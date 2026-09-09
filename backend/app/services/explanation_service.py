"""SHAP explanation for a stored customer.

A thin adapter over the Step 3 explainer. No SHAP mathematics happens here: the
backend fetches the record, hands it to ``explain_customer``, and republishes the
result unchanged — including ``explained_output`` and ``base_value``, which are
what make the numbers interpretable.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ExplanationFailedError, ModelUnavailableError
from app.schemas.explanation import (
    ExplanationResponse,
    GlobalDriver,
    GlobalImportanceResponse,
)
from app.schemas.prediction import RiskDriver
from app.services import customer_service
from app.services.ml_runtime import models_dir, translate_ml_errors
from ml.src import config as ml_config
from ml.src.explainability.explainer import explain_customer


# =========================================================
# 1. EXPLAIN A RECORD
# =========================================================


def explain_record(customer_record: Mapping[str, Any], top_k: int) -> dict[str, Any]:
    """Run the real SHAP explainer on an already-fetched customer record.

    Returned as the explainer's own dictionary so the Step 3 contract passes
    through untouched.
    """
    with translate_ml_errors("Explanation", ExplanationFailedError):
        return explain_customer(customer_record, top_k=top_k, models_dir=models_dir())


# =========================================================
# 2. EXPLAIN A STORED CUSTOMER
# =========================================================


def explain_customer_by_id(
    session: Session, customer_id: str, top_k: int | None = None
) -> dict[str, Any]:
    """Explain the churn prediction for a customer held in the database."""
    record = customer_service.get_customer_record(session, customer_id)
    drivers_requested = top_k if top_k is not None else get_settings().explanation_top_k

    explanation = explain_record(record, top_k=drivers_requested)

    # The explainer echoes back whatever identifier the record carried; the
    # database identifier is authoritative here.
    explanation["customer_id"] = customer_id
    return explanation


# =========================================================
# 3. API RESPONSE
# =========================================================


def explain_for_customer(
    session: Session, customer_id: str, top_k: int | None = None
) -> ExplanationResponse:
    """Explain a stored customer and project onto the API schema.

    Field names and values are taken from the explainer unchanged, including
    ``explained_output = "log_odds"`` and ``base_value``.
    """
    explanation = explain_customer_by_id(session, customer_id, top_k=top_k)
    return ExplanationResponse(
        customer_id=explanation["customer_id"],
        churn_probability=explanation["churn_probability"],
        prediction=explanation["prediction"],
        risk_level=explanation["risk_level"],
        model_version=explanation["model_version"],
        explained_output=explanation["explained_output"],
        base_value=explanation["base_value"],
        top_drivers=[RiskDriver(**driver) for driver in explanation["top_drivers"]],
    )


# =========================================================
# 4. GLOBAL IMPORTANCE (STORED ARTIFACT)
# =========================================================


def get_global_importance(top_k: int = 8) -> GlobalImportanceResponse:
    """Return the stored global SHAP ranking. Does not recompute explanations.

    The CSV is produced by the locked explainability pipeline. Reading it on
    dashboard load is cheap and keeps 7k local SHAP calls off the request path.
    """
    from ml.src.explainability.global_importance import GLOBAL_IMPORTANCE_FILENAME

    directory = Path(models_dir()) if models_dir() else ml_config.MODELS_DIR
    path = directory / GLOBAL_IMPORTANCE_FILENAME
    if not path.exists():
        raise ModelUnavailableError(
            "Global SHAP importance is not available on this server. "
            "Generate it with `python -m ml.src.explainability.global_importance`."
        )

    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    drivers: list[GlobalDriver] = []
    for row in rows:
        try:
            drivers.append(
                GlobalDriver(
                    feature=str(row["feature"]),
                    mean_absolute_shap=float(row["mean_absolute_shap"]),
                    mean_signed_shap=float(row["mean_signed_shap"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    drivers.sort(key=lambda item: item.mean_absolute_shap, reverse=True)
    return GlobalImportanceResponse(drivers=drivers[: max(1, top_k)])
