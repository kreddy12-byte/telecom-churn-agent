"""Data access for human-review actions."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.action import STATUS_PENDING, Action


# =========================================================
# 1. WRITES
# =========================================================


def create_action(
    session: Session,
    customer_id: str,
    strategy_id: str,
    recommendation: str,
    reviewer_note: str | None = None,
) -> Action:
    """Create an action in PENDING state.

    The status is not a parameter. An action that could be created already
    approved would let a caller bypass human review entirely, so the only way
    into a decided state is an explicit update.
    """
    action = Action(
        customer_id=customer_id,
        strategy_id=strategy_id,
        recommendation=recommendation,
        status=STATUS_PENDING,
        reviewer_note=reviewer_note,
    )
    session.add(action)
    session.flush()
    return action


def apply_review(
    session: Session,
    action: Action,
    new_status: str,
    reviewer_note: str | None,
    recommendation: str | None = None,
    reviewed_by_sub: str | None = None,
    reviewed_by_email: str | None = None,
    reviewed_by_name: str | None = None,
) -> Action:
    """Record a reviewer's decision on an existing action.

    Transition legality is checked by the service before this is called; the
    repository performs the write.
    """
    action.status = new_status
    if reviewer_note is not None:
        action.reviewer_note = reviewer_note
    if recommendation is not None:
        action.recommendation = recommendation
    if reviewed_by_sub is not None:
        action.reviewed_by_sub = reviewed_by_sub
        action.reviewed_by_email = reviewed_by_email
        action.reviewed_by_name = reviewed_by_name
    session.flush()
    return action


# =========================================================
# 2. READS
# =========================================================


def get_action(session: Session, action_id: int) -> Action | None:
    """Fetch one action by id, or None when absent."""
    return session.get(Action, action_id)


def list_actions(
    session: Session,
    customer_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Action]:
    """Fetch a page of actions, newest first, with optional filters."""
    statement = select(Action)
    if customer_id is not None:
        statement = statement.where(Action.customer_id == customer_id)
    if status is not None:
        statement = statement.where(Action.status == status)

    statement = statement.order_by(Action.id.desc()).limit(limit).offset(offset)
    return list(session.scalars(statement))


def count_actions(
    session: Session, customer_id: str | None = None, status: str | None = None
) -> int:
    """Number of actions matching the same filters as :func:`list_actions`."""
    statement = select(func.count()).select_from(Action)
    if customer_id is not None:
        statement = statement.where(Action.customer_id == customer_id)
    if status is not None:
        statement = statement.where(Action.status == status)
    return int(session.scalar(statement) or 0)


def latest_for_customers(session: Session, customer_ids: Sequence[str]) -> dict[str, Action]:
    """Most recent action per customer, keyed by identifier."""
    ids = list(customer_ids)
    if not ids:
        return {}

    newest_ids = session.scalars(
        select(func.max(Action.id))
        .where(Action.customer_id.in_(ids))
        .group_by(Action.customer_id)
    ).all()
    if not newest_ids:
        return {}

    rows = session.scalars(select(Action).where(Action.id.in_(newest_ids)))
    return {action.customer_id: action for action in rows}


def counts_by_status(session: Session) -> dict[str, int]:
    """How many actions sit in each review status."""
    rows = session.execute(select(Action.status, func.count()).group_by(Action.status))
    return {status: int(count) for status, count in rows}
