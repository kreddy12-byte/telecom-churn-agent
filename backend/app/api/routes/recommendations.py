"""Retention recommendation endpoint.

The LLM provider is injected by a dependency that reads environment variables
once. Route handlers never see an API key.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.responses import MODEL_ERRORS
from app.core.auth import get_authenticated_user
from app.core.dependencies import ProviderDep, SessionDep
from app.schemas.recommendation import (
    DetailedRecommendationResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from app.services import recommendation_service

router = APIRouter(tags=["recommendations"], dependencies=[Depends(get_authenticated_user)])


@router.post(
    "/recommendation",
    response_model=None,
    status_code=status.HTTP_200_OK,
    responses=MODEL_ERRORS,
    summary="Generate a retention recommendation",
    description=(
        "Builds SHAP evidence for a stored customer and asks the existing "
        "retention agent for a recommendation. By default the compact Step 1 "
        "contract is returned. Set `detailed` to true for the full agent "
        "output (strategy, reasoning, evidence, confidence rationale). "
        "`requires_human_approval` is always true. An unavailable LLM falls "
        "back to the deterministic strategy engine; the response says so."
    ),
)
def recommend(
    request: RecommendationRequest,
    session: SessionDep,
    provider: ProviderDep,
) -> RecommendationResponse | DetailedRecommendationResponse:
    recommendation = recommendation_service.recommend_for_customer(
        session, request.customer_id, provider=provider
    )
    if request.detailed:
        return recommendation
    return RecommendationResponse(**recommendation.to_api_contract())
