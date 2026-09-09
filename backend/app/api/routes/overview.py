"""Reviewer overview aggregates."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import get_authenticated_user
from app.core.dependencies import SessionDep
from app.schemas.overview import OverviewResponse
from app.services import overview_service

router = APIRouter(tags=["overview"], dependencies=[Depends(get_authenticated_user)])


@router.get(
    "/overview",
    response_model=OverviewResponse,
    summary="Population and review counts",
    description=(
        "Counts taken from stored customers, predictions, and actions. "
        "This endpoint never runs the model and never invents a metric."
    ),
)
def get_overview(session: SessionDep) -> OverviewResponse:
    return overview_service.get_overview(session)
