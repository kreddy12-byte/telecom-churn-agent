"""Human-review action tracking.

These endpoints record decisions. They send no message, change no plan, and
call no external system. Approving an action means a human approved it.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.responses import ACTION_NOT_FOUND, CUSTOMER_NOT_FOUND, REVIEW_ERRORS
from app.core.auth import get_authenticated_user
from app.core.dependencies import AuthenticatedUserDep, PaginationDep, SessionDep
from app.schemas.action import (
    ActionCreate,
    ActionListResponse,
    ActionResponse,
    ActionReview,
    ActionStatus,
)
from app.services import action_service

router = APIRouter(
    prefix="/actions",
    tags=["actions"],
    dependencies=[Depends(get_authenticated_user)],
)


@router.post(
    "",
    response_model=ActionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=CUSTOMER_NOT_FOUND,
    summary="Create a pending review action",
    description=(
        "Raises a retention recommendation for human review. The status is "
        "always `PENDING` — there is no request a caller can send that creates "
        "an already-approved action. No customer is contacted."
    ),
)
def create_action(payload: ActionCreate, session: SessionDep) -> ActionResponse:
    return action_service.create_action(session, payload)


@router.get(
    "",
    response_model=ActionListResponse,
    summary="List review actions",
    description="Returns a page of actions, newest first. Filter by customer or status.",
)
def list_actions(
    session: SessionDep,
    pagination: PaginationDep,
    customer_id: Annotated[str | None, Query(description="Restrict to one customer.")] = None,
    status_filter: Annotated[
        ActionStatus | None,
        Query(alias="status", description="Restrict to one review status."),
    ] = None,
) -> ActionListResponse:
    return action_service.list_actions(
        session,
        customer_id=customer_id,
        status=status_filter,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(
    "/{action_id}",
    response_model=ActionResponse,
    responses=ACTION_NOT_FOUND,
    summary="Get one review action",
)
def get_action(action_id: int, session: SessionDep) -> ActionResponse:
    return action_service.get_action(session, action_id)


@router.patch(
    "/{action_id}",
    response_model=ActionResponse,
    responses=REVIEW_ERRORS,
    summary="Record a human review decision",
    description=(
        "The only path from `PENDING` to a decided state. Allowed transitions: "
        "`PENDING → APPROVED | MODIFIED | REJECTED`, then "
        "`MODIFIED → APPROVED | REJECTED`. `APPROVED` and `REJECTED` are "
        "terminal. A reviewer note is required for `MODIFIED` and `REJECTED`. "
        "This update changes only the stored record; it performs no external action."
    ),
)
def review_action(
    action_id: int,
    review: ActionReview,
    session: SessionDep,
    reviewer: AuthenticatedUserDep,
) -> ActionResponse:
    return action_service.review_action(session, action_id, review, reviewer)
