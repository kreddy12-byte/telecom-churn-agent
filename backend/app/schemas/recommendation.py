"""Retention recommendation contracts.

``RecommendationResponse`` is the compact Step 1 contract. The full agent output
— selected strategy, reasoning, SHAP-backed supporting evidence, confidence
rationale, limitations, provenance — is returned as
``DetailedRecommendationResponse``, which is the agent's own
``RetentionRecommendation`` model re-used verbatim rather than copied. Copying it
would create a second definition of the same contract that could drift.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from agent.models.recommendation import RetentionRecommendation

# Re-exported under an API-facing name so the OpenAPI schema reads naturally.
DetailedRecommendationResponse = RetentionRecommendation


class RecommendationRequest(BaseModel):
    """Request body for ``POST /api/recommendation``."""

    customer_id: str = Field(..., min_length=1, examples=["7590-VHVEG"])
    detailed: bool = Field(
        default=False,
        description=(
            "Return the full agent output (strategy, reasoning, evidence, confidence "
            "rationale, provenance) instead of the compact contract."
        ),
    )


class RecommendationResponse(BaseModel):
    """Compact recommendation contract."""

    customer_id: str
    recommendation: str
    reason: str
    priority: Literal["LOW", "MEDIUM", "HIGH"]
    confidence: Literal["LOW", "MEDIUM", "HIGH"]
    requires_human_approval: Literal[True] = Field(
        default=True,
        description="Always true. The agent is decision support and cannot self-authorise.",
    )


__all__ = [
    "DetailedRecommendationResponse",
    "RecommendationRequest",
    "RecommendationResponse",
]
