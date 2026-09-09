"""Customer read operations.

The list endpoint joins in each customer's most recent stored prediction rather
than scoring them on demand: a page of 20 customers must cost one page of
database reads, not 20 model inferences.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import CustomerNotFoundError
from app.db.models.customer import Customer
from app.db.repositories import action_repository, customer_repository, prediction_repository
from app.schemas.customer import (
    CustomerDetail,
    CustomerListResponse,
    CustomerSummary,
    LatestAction,
    LatestPrediction,
)
from app.schemas.common import PageMeta


# =========================================================
# 1. LOOKUP
# =========================================================


def get_customer_or_error(session: Session, customer_id: str) -> Customer:
    """Fetch a customer, raising the API's 404 error when absent.

    Every service that needs a customer goes through this, so "unknown customer"
    is reported identically by every endpoint.
    """
    customer = customer_repository.get_customer(session, customer_id)
    if customer is None:
        raise CustomerNotFoundError(customer_id)
    return customer


def get_customer_record(session: Session, customer_id: str) -> dict[str, Any]:
    """Fetch a customer as the record shape the ML pipeline expects."""
    return get_customer_or_error(session, customer_id).to_model_record()


# =========================================================
# 2. READ ENDPOINTS
# =========================================================


def get_customer_detail(session: Session, customer_id: str) -> CustomerDetail:
    """Full profile for one customer, with their latest stored prediction."""
    customer = get_customer_or_error(session, customer_id)
    latest = prediction_repository.latest_for_customer(session, customer_id)

    detail = CustomerDetail.model_validate(customer)
    if latest is not None:
        detail.latest_prediction = LatestPrediction.model_validate(latest)
    latest_actions = action_repository.latest_for_customers(session, [customer_id])
    action = latest_actions.get(customer_id)
    if action is not None:
        detail.latest_action = LatestAction.model_validate(action)
    return detail


def build_customer_summaries(
    session: Session, customers: list[Customer]
) -> list[CustomerSummary]:
    ids = [customer.customer_id for customer in customers]
    latest_by_customer = prediction_repository.latest_for_customers(session, ids)
    actions_by_customer = action_repository.latest_for_customers(session, ids)

    items: list[CustomerSummary] = []
    for customer in customers:
        summary = CustomerSummary.model_validate(customer)
        prediction = latest_by_customer.get(customer.customer_id)
        if prediction is not None:
            summary.latest_prediction = LatestPrediction.model_validate(prediction)
        action = actions_by_customer.get(customer.customer_id)
        if action is not None:
            summary.latest_action = LatestAction.model_validate(action)
        items.append(summary)
    return items


def list_customers(
    session: Session,
    limit: int,
    offset: int,
    query: str | None = None,
    risk_level: str | None = None,
) -> CustomerListResponse:
    """A page of customers, each with their latest stored prediction and action."""
    customers = customer_repository.list_customers(
        session, limit=limit, offset=offset, query=query, risk_level=risk_level
    )
    total = customer_repository.count_customers(session, query=query, risk_level=risk_level)
    items = build_customer_summaries(session, customers)
    return CustomerListResponse(
        items=items, meta=PageMeta(total=total, limit=limit, offset=offset)
    )
