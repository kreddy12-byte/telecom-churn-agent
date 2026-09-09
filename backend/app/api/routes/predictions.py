"""Churn prediction endpoints.

Declared with ``def`` rather than ``async def`` on purpose: model inference is
blocking CPU work, and a synchronous handler is run by FastAPI in a worker
thread instead of stalling the event loop.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from app.api.responses import BATCH_ERRORS, MODEL_ERRORS
from app.core.auth import get_authenticated_user
from app.core.dependencies import PaginationDep, SessionDep
from app.schemas.prediction import (
    BatchScoringResponse,
    PredictionRankingResponse,
    PredictionRequest,
    PredictionResponse,
    PredictionSummaryResponse,
    ProbabilityDistributionResponse,
)
from app.services import batch_scoring_service, prediction_service

router = APIRouter(tags=["predictions"], dependencies=[Depends(get_authenticated_user)])


@router.post(
    "/predict",
    response_model=PredictionResponse,
    status_code=status.HTTP_200_OK,
    responses=MODEL_ERRORS,
    summary="Predict churn for a customer",
    description=(
        "Scores a stored customer with the trained model and appends the result "
        "to their prediction history. The probability, risk band, and SHAP "
        "drivers all come from the ML layer; the API computes none of them."
    ),
)
def predict(request: PredictionRequest, session: SessionDep) -> PredictionResponse:
    return prediction_service.predict_for_customer(session, request.customer_id)


@router.post(
    "/predictions/batch",
    response_model=BatchScoringResponse,
    status_code=status.HTTP_200_OK,
    responses=BATCH_ERRORS,
    summary="Score every stored customer",
    description=(
        "Loads customers in chunks and scores them with the same saved production "
        "model used by `POST /api/predict`. Does not compute SHAP values and does "
        "not call the retention agent. Each run appends one history row per "
        "customer; ranking and summary always use the latest row."
    ),
)
def score_all_customers(session: SessionDep) -> BatchScoringResponse:
    return batch_scoring_service.score_all_customers(session)


@router.get(
    "/predictions/ranking",
    response_model=PredictionRankingResponse,
    summary="Rank customers by latest churn probability",
    description=(
        "Returns the latest stored prediction per customer, highest probability "
        "first. Does not run the model, SHAP, or the retention agent."
    ),
)
def rank_predictions(
    session: SessionDep,
    pagination: PaginationDep,
    risk: Annotated[
        Literal["LOW", "MEDIUM", "HIGH"] | None,
        Query(description="Keep customers whose latest stored prediction is in this band."),
    ] = None,
) -> PredictionRankingResponse:
    return batch_scoring_service.rank_latest_predictions(
        session,
        risk=risk,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(
    "/predictions/summary",
    response_model=PredictionSummaryResponse,
    summary="Latest prediction distribution",
    description=(
        "HIGH / MEDIUM / LOW counts and probability stats from each customer's "
        "most recent stored prediction. Historical rows are not double-counted."
    ),
)
def prediction_summary(session: SessionDep) -> PredictionSummaryResponse:
    return batch_scoring_service.summarize_latest_predictions(session)


@router.get(
    "/predictions/distribution",
    response_model=ProbabilityDistributionResponse,
    summary="Churn probability histogram",
    description=(
        "Counts latest stored predictions into 10-point probability bands. "
        "Does not run the model. Historical rows are not double-counted."
    ),
)
def prediction_distribution(session: SessionDep) -> ProbabilityDistributionResponse:
    return batch_scoring_service.probability_distribution(session)
