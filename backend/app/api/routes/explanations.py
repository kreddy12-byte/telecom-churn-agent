"""SHAP explanation endpoint.

A thin HTTP adapter over the Step 3 explainer. No SHAP mathematics happens here.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.responses import MODEL_ERRORS
from app.core.auth import get_authenticated_user
from app.core.dependencies import SessionDep
from app.schemas.explanation import ExplanationResponse, GlobalImportanceResponse
from app.services import explanation_service

router = APIRouter(
    prefix="/customers",
    tags=["explanations"],
    dependencies=[Depends(get_authenticated_user)],
)

# Separate router so this path cannot be captured by /customers/{customer_id}.
importance_router = APIRouter(
    tags=["explanations"],
    dependencies=[Depends(get_authenticated_user)],
)


@router.get(
    "/{customer_id}/explanation",
    response_model=ExplanationResponse,
    responses=MODEL_ERRORS,
    summary="Explain a customer's churn prediction",
    description=(
        "Returns the real SHAP explanation for a stored customer. "
        "`explained_output` is always `log_odds`: SHAP values here are "
        "contributions to the model's log-odds, not to a probability. "
        "The backend does not recompute SHAP; it calls the existing explainer."
    ),
)
def get_explanation(
    customer_id: str,
    session: SessionDep,
    top_k: Annotated[
        int,
        Query(ge=1, le=19, description="Number of drivers to return, ranked by absolute contribution."),
    ] = 5,
) -> ExplanationResponse:
    return explanation_service.explain_for_customer(session, customer_id, top_k=top_k)


@importance_router.get(
    "/explanations/global-importance",
    response_model=GlobalImportanceResponse,
    responses={
        503: MODEL_ERRORS[503],
    },
    summary="Global SHAP feature importance",
    description=(
        "Returns the stored global SHAP ranking from the training-time artifact. "
        "This endpoint does not recompute SHAP and does not inspect individual customers."
    ),
)
def global_importance(
    top_k: Annotated[
        int,
        Query(ge=1, le=19, description="Number of original features to return, ranked by mean |SHAP|."),
    ] = 8,
) -> GlobalImportanceResponse:
    return explanation_service.get_global_importance(top_k=top_k)
