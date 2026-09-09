"""Bridge from the ML/SHAP layers to agent evidence.

``explain_customer`` already calls the predictor internally and returns both the
prediction and the SHAP drivers, so this module makes a single call rather than
running the model twice.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from agent.config import get_agent_settings
from agent.models.evidence import CustomerEvidence
from ml.src.explainability.explainer import explain_customer
from ml.src.prediction.predictor import load_customer_from_dataset

# =========================================================
# 1. BUILD EVIDENCE FROM A CUSTOMER RECORD
# =========================================================


def sanitise_profile(customer_data: Mapping[str, Any]) -> dict[str, Any]:
    """Copy a customer record with plain Python scalars throughout."""
    return {key: _to_python_scalar(value) for key, value in dict(customer_data).items()}


def _to_python_scalar(value: Any) -> Any:
    """Convert numpy/pandas scalars to plain Python values.

    Records read from pandas carry numpy types, which would break JSON
    serialisation of the evidence and of the LLM prompt.
    """
    if isinstance(value, np.generic):
        return value.item()
    if value is not None and not isinstance(value, (str, bool)) and pd.isna(value):
        return None
    return value


def build_customer_evidence(
    customer_data: Mapping[str, Any],
    top_k: int | None = None,
    models_dir: Path | None = None,
) -> CustomerEvidence:
    """Run prediction + SHAP for one customer and package the result.

    Args:
        customer_data: Raw customer record in the dataset's original schema.
        top_k: Number of SHAP drivers to evaluate. Defaults to
            ``AGENT_EVIDENCE_DRIVER_COUNT``; more drivers than a report shows,
            because the strategy engine benefits from seeing the fuller picture.
        models_dir: Override for the model artifact directory (used by tests).
    """
    driver_count = top_k if top_k is not None else get_agent_settings().agent_evidence_driver_count

    explanation = explain_customer(customer_data, top_k=driver_count, models_dir=models_dir)

    # The profile is what lets generated text quote real values (for example the
    # customer's actual contract type) instead of inventing them.
    return CustomerEvidence.from_explanation(
        explanation, customer_profile=sanitise_profile(customer_data)
    )


# =========================================================
# 2. CONVENIENCE: EVIDENCE STRAIGHT FROM THE DATASET
# =========================================================


def build_evidence_for_dataset_customer(
    customer_id: str,
    top_k: int | None = None,
    models_dir: Path | None = None,
) -> CustomerEvidence:
    """Look a customer up in the raw dataset and build their evidence.

    Used for local verification and demos; the backend will pass records from the
    database instead.
    """
    customer_data = load_customer_from_dataset(row=None, customer_id=customer_id)
    return build_customer_evidence(customer_data, top_k=top_k, models_dir=models_dir)
