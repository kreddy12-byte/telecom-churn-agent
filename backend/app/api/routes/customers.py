"""Customer read endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.api.responses import CUSTOMER_NOT_FOUND
from app.core.auth import get_authenticated_user
from app.core.dependencies import PaginationDep, SessionDep
from app.schemas.customer import CustomerDetail, CustomerListResponse
from app.services import customer_service

router = APIRouter(
    prefix="/customers",
    tags=["customers"],
    dependencies=[Depends(get_authenticated_user)],
)


@router.get(
    "",
    response_model=CustomerListResponse,
    summary="List customers",
    description=(
        "Returns a page of customers, each with their most recent **stored** "
        "prediction if one exists. This endpoint never runs the model: use "
        "`POST /api/predict` to score a customer."
    ),
)
def list_customers(
    session: SessionDep,
    pagination: PaginationDep,
    q: Annotated[
        str | None,
        Query(description="Case-insensitive substring match on customer_id."),
    ] = None,
    risk_level: Annotated[
        Literal["LOW", "MEDIUM", "HIGH"] | None,
        Query(description="Keep customers whose latest stored prediction is in this band."),
    ] = None,
) -> CustomerListResponse:
    return customer_service.list_customers(
        session,
        limit=pagination.limit,
        offset=pagination.offset,
        query=q,
        risk_level=risk_level,
    )


@router.get(
    "/{customer_id}",
    response_model=CustomerDetail,
    responses=CUSTOMER_NOT_FOUND,
    summary="Get one customer",
    description="Returns the full profile — every feature the churn model consumes.",
)
def get_customer(customer_id: str, session: SessionDep) -> CustomerDetail:
    return customer_service.get_customer_detail(session, customer_id)
