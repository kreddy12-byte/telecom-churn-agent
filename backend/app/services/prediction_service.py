"""Churn prediction for a stored customer, with history persistence.

``predict_for_customer`` (this module) and ``batch_scoring_service.score_all_customers``
are the only writers of the predictions table. Recommendation and what-if
requests also run the model, but they are analyses of the current state rather
than scoring events, so they leave the history alone.

The probability itself is never computed here. ``explain_customer`` calls the
Step 2 predictor internally and returns both the prediction and the SHAP drivers
in one pass, so the endpoint's documented response shape costs a single trip
through the model.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.repositories import prediction_repository
from app.schemas.prediction import PredictionResponse, RiskDriver
from app.services import explanation_service

logger = get_logger(__name__)


# =========================================================
# 1. PREDICT AND PERSIST
# =========================================================


def predict_for_customer(
    session: Session, customer_id: str, top_k: int | None = None
) -> PredictionResponse:
    """Score a stored customer, append the result to their history, and return it.

    Raises:
        CustomerNotFoundError: The customer is not in the database.
        InvalidCustomerDataError: The stored record cannot be scored.
        ModelUnavailableError: Trained artifacts are missing or unreadable.
    """
    drivers_requested = top_k if top_k is not None else get_settings().explanation_top_k
    explanation = explanation_service.explain_customer_by_id(
        session, customer_id, top_k=drivers_requested
    )

    stored = prediction_repository.create_prediction(
        session,
        customer_id=customer_id,
        churn_probability=explanation["churn_probability"],
        risk_level=explanation["risk_level"],
        model_version=explanation["model_version"],
    )
    session.commit()

    logger.info(
        "Stored prediction for %s: %.4f (%s)",
        customer_id,
        explanation["churn_probability"],
        explanation["risk_level"],
    )

    return PredictionResponse(
        customer_id=customer_id,
        churn_probability=explanation["churn_probability"],
        risk_level=explanation["risk_level"],
        prediction=explanation["prediction"],
        model_version=explanation["model_version"],
        top_drivers=[RiskDriver(**driver) for driver in explanation["top_drivers"]],
        predicted_at=stored.created_at,
    )
