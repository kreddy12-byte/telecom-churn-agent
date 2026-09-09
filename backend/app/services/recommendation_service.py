"""Retention recommendations for a stored customer.

The backend's job here is narrow: fetch the record, hand it to the Step 4 agent,
return what comes back. Strategy selection, LLM reasoning, guardrails, the
deterministic fallback, and the confidence model all stay in ``agent/``.

The LLM provider is injected by the route's dependency, so no API key is read,
held, or logged anywhere in this module.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from agent.models.recommendation import RetentionRecommendation
from agent.providers.base import LLMProvider
from agent.services.evidence_builder import build_customer_evidence
from agent.services.recommendation_service import RecommendationService
from app.core.errors import RecommendationFailedError
from app.core.logging import get_logger
from app.services import customer_service
from app.services.ml_runtime import models_dir, translate_ml_errors

logger = get_logger(__name__)


# =========================================================
# 1. RECOMMEND FOR A STORED CUSTOMER
# =========================================================


def recommend_for_customer(
    session: Session, customer_id: str, provider: LLMProvider | None = None
) -> RetentionRecommendation:
    """Produce a human-approvable recommendation for one customer.

    An unavailable LLM is not a failure: the agent falls back to its
    deterministic strategy engine, labels the output accordingly, and still
    returns a complete recommendation.
    """
    record = customer_service.get_customer_record(session, customer_id)

    # Prediction + SHAP in one pass; the evidence builder owns that call.
    with translate_ml_errors("Recommendation", RecommendationFailedError):
        evidence = build_customer_evidence(record, models_dir=models_dir())

    recommendation = RecommendationService(provider=provider).recommend(evidence)

    logger.info(
        "Recommendation for %s: %s (provider=%s, confidence=%s)",
        customer_id,
        recommendation.selected_strategy.strategy_id,
        recommendation.provider,
        recommendation.confidence,
    )
    return recommendation
