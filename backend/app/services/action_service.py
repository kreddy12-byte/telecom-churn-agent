"""Human-review action tracking.

This service records decisions. It sends nothing, changes no subscription, and
calls no external system — approving an action means a human approved it, and
nothing else happens as a result.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser
from app.core.errors import (
    ActionNotFoundError,
    InvalidActionTransitionError,
    ReviewerNoteRequiredError,
)
from app.core.logging import get_logger
from app.db.models.action import (
    ALLOWED_TRANSITIONS,
    STATUS_MODIFIED,
    STATUS_PENDING,
    STATUSES_REQUIRING_NOTE,
    Action,
)
from app.db.repositories import action_repository
from app.schemas.action import ActionCreate, ActionListResponse, ActionResponse, ActionReview
from app.schemas.common import PageMeta
from app.services import customer_service

logger = get_logger(__name__)


# =========================================================
# 1. CREATE (ALWAYS PENDING)
# =========================================================


def create_action(session: Session, payload: ActionCreate) -> ActionResponse:
    """Raise a new action for human review.

    The status is not taken from the request. Every action starts PENDING, which
    is what makes "no action is ever auto-approved" a property of the system
    rather than a convention callers are trusted to follow.
    """
    # Fails with a 404 rather than a foreign-key error from the driver.
    customer_service.get_customer_or_error(session, payload.customer_id)

    action = action_repository.create_action(
        session,
        customer_id=payload.customer_id,
        strategy_id=payload.strategy_id,
        recommendation=payload.recommendation,
        reviewer_note=payload.reviewer_note,
    )
    session.commit()

    logger.info(
        "Action %d created for %s (%s) in status %s",
        action.id,
        action.customer_id,
        action.strategy_id,
        STATUS_PENDING,
    )
    return ActionResponse.model_validate(action)


# =========================================================
# 2. READ
# =========================================================


def get_action(session: Session, action_id: int) -> ActionResponse:
    """Fetch one action, or raise the API's 404 error."""
    return ActionResponse.model_validate(_get_action_or_error(session, action_id))


def list_actions(
    session: Session,
    customer_id: str | None,
    status: str | None,
    limit: int,
    offset: int,
) -> ActionListResponse:
    """A page of actions, newest first, optionally filtered."""
    actions = action_repository.list_actions(
        session, customer_id=customer_id, status=status, limit=limit, offset=offset
    )
    total = action_repository.count_actions(session, customer_id=customer_id, status=status)

    return ActionListResponse(
        items=[ActionResponse.model_validate(action) for action in actions],
        meta=PageMeta(total=total, limit=limit, offset=offset),
    )


def _get_action_or_error(session: Session, action_id: int) -> Action:
    action = action_repository.get_action(session, action_id)
    if action is None:
        raise ActionNotFoundError(action_id)
    return action


# =========================================================
# 3. REVIEW (THE ONLY PATH TO A DECIDED STATE)
# =========================================================


def review_action(
    session: Session,
    action_id: int,
    review: ActionReview,
    reviewer: AuthenticatedUser,
) -> ActionResponse:
    """Record a reviewer's decision on an action.

    Raises:
        ActionNotFoundError: No such action.
        InvalidActionTransitionError: The workflow does not permit the change —
            for instance re-deciding an action that is already APPROVED.
        ReviewerNoteRequiredError: MODIFIED and REJECTED need a stated reason.
    """
    action = _get_action_or_error(session, action_id)

    _check_transition_allowed(action, review.status)
    _check_note_supplied(action, review)

    updated = action_repository.apply_review(
        session,
        action,
        new_status=review.status,
        reviewer_note=review.reviewer_note,
        # Revised wording is only accepted alongside a MODIFIED decision; an
        # approval must apply to the recommendation as it was reviewed.
        recommendation=review.recommendation if review.status == STATUS_MODIFIED else None,
        reviewed_by_sub=reviewer.sub,
        reviewed_by_email=reviewer.email,
        reviewed_by_name=reviewer.name,
    )
    session.commit()

    logger.info("Action %d reviewed: %s by %s", action_id, review.status, reviewer.sub)
    return ActionResponse.model_validate(updated)


def _check_transition_allowed(action: Action, new_status: str) -> None:
    if not action.can_transition_to(new_status):
        raise InvalidActionTransitionError(
            current_status=action.status,
            requested_status=new_status,
            allowed=sorted(ALLOWED_TRANSITIONS.get(action.status, frozenset())),
        )


def _check_note_supplied(action: Action, review: ActionReview) -> None:
    """A changed or refused recommendation must carry a reason.

    An existing note on the action counts: the reviewer may have recorded their
    reasoning when the action was raised.
    """
    if review.status not in STATUSES_REQUIRING_NOTE:
        return

    supplied = (review.reviewer_note or action.reviewer_note or "").strip()
    if not supplied:
        raise ReviewerNoteRequiredError(review.status)
