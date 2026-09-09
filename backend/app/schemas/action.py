"""Human-review action contracts.

The status vocabulary is uppercase and shared with the database layer. A created
action is always PENDING — ``ActionCreate`` has no status field at all, so there
is no request a caller could send that produces an approved action.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PageMeta

# Mirrors app.db.models.action; kept as a Literal so FastAPI validates and
# documents the allowed values.
ActionStatus = Literal["PENDING", "APPROVED", "MODIFIED", "REJECTED"]

# The three decisions a human reviewer can record. PENDING is excluded: an
# action cannot be moved back to awaiting review.
ReviewDecision = Literal["APPROVED", "MODIFIED", "REJECTED"]


class ActionCreate(BaseModel):
    """Request body for ``POST /api/actions``."""

    customer_id: str = Field(..., min_length=1, examples=["7590-VHVEG"])
    strategy_id: str = Field(..., min_length=1, examples=["CONTRACT_CONVERSION"])
    recommendation: str = Field(..., min_length=1)
    reviewer_note: str | None = Field(
        default=None, description="Optional context recorded when the action is raised."
    )


class ActionReview(BaseModel):
    """Request body for ``PATCH /api/actions/{action_id}``."""

    status: ReviewDecision = Field(..., description="The reviewer's decision.")
    reviewer_note: str | None = Field(
        default=None,
        description=(
            "Required for MODIFIED and REJECTED, so a changed or refused "
            "recommendation is always accompanied by a reason."
        ),
    )
    recommendation: str | None = Field(
        default=None,
        min_length=1,
        description="Revised wording, permitted when the decision is MODIFIED.",
    )


class ActionResponse(BaseModel):
    """A stored action record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: str
    strategy_id: str
    recommendation: str
    status: ActionStatus
    reviewer_note: str | None = None
    reviewed_by_sub: str | None = None
    reviewed_by_email: str | None = None
    reviewed_by_name: str | None = None
    created_at: datetime
    updated_at: datetime


class ActionListResponse(BaseModel):
    """A page of actions plus pagination metadata."""

    items: list[ActionResponse]
    meta: PageMeta
