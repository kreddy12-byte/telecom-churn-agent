"""Read-only population and review aggregates.

These numbers are counted from stored rows. The overview never runs the model.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.action import ACTION_STATUSES
from app.db.models.customer import Customer
from app.db.repositories import action_repository, customer_repository, prediction_repository
from app.schemas.overview import OverviewResponse
from app.services import customer_service


def get_overview(session: Session) -> OverviewResponse:
    """Build the reviewer overview from existing tables."""
    risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    risk_counts.update(prediction_repository.latest_risk_counts(session))

    action_counts = {status: 0 for status in ACTION_STATUSES}
    action_counts.update(action_repository.counts_by_status(session))

    high_risk_predictions = prediction_repository.recent_high_risk(session, limit=8)
    high_risk_ids = [row.customer_id for row in high_risk_predictions]
    customers = [
        customer
        for customer_id in high_risk_ids
        if (customer := session.get(Customer, customer_id)) is not None
    ]

    return OverviewResponse(
        customer_count=customer_repository.count_customers(session),
        evaluated_count=prediction_repository.count_evaluated_customers(session),
        risk_counts=risk_counts,
        action_counts=action_counts,
        recent_high_risk=customer_service.build_customer_summaries(session, customers),
    )
