"""Action table — the record of a human decision on a recommendation.

This table is deliberately the only place in the system where a *decision* is
stored, and it stores nothing else: no message is sent, no plan is changed, no
external system is called. Approving an action records that a human approved it.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# =========================================================
# 1. STATUS AND ALLOWED TRANSITIONS
# =========================================================

STATUS_PENDING = "PENDING"
STATUS_APPROVED = "APPROVED"
STATUS_MODIFIED = "MODIFIED"
STATUS_REJECTED = "REJECTED"

ACTION_STATUSES: tuple[str, ...] = (
    STATUS_PENDING,
    STATUS_APPROVED,
    STATUS_MODIFIED,
    STATUS_REJECTED,
)

# The review workflow as a state machine.
#
# PENDING is the only entry point — an action can never be created approved.
# MODIFIED is not terminal: a reviewer may revise the wording and a second
# reviewer may then sign it off or turn it down. APPROVED and REJECTED are final,
# so a decision cannot be quietly reversed after the fact; a new action must be
# raised instead.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    STATUS_PENDING: frozenset({STATUS_APPROVED, STATUS_MODIFIED, STATUS_REJECTED}),
    STATUS_MODIFIED: frozenset({STATUS_APPROVED, STATUS_REJECTED}),
    STATUS_APPROVED: frozenset(),
    STATUS_REJECTED: frozenset(),
}

# A reviewer who changes or turns down a recommendation must say why; approving
# the recommendation as written needs no extra justification.
STATUSES_REQUIRING_NOTE: frozenset[str] = frozenset({STATUS_MODIFIED, STATUS_REJECTED})


# =========================================================
# 2. ACTION TABLE
# =========================================================


class Action(Base):
    """A retention recommendation awaiting, or carrying, a human decision."""

    __tablename__ = "actions"
    __table_args__ = (
        Index("ix_actions_customer_status", "customer_id", "status"),
        Index("ix_actions_status", "status"),
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'MODIFIED', 'REJECTED')",
            name="ck_actions_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False
    )

    # The strategy the recommendation came from, kept as a plain string: the
    # catalogue lives in the agent layer and is versioned with the code, not
    # with the database.
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=STATUS_PENDING, server_default=STATUS_PENDING
    )
    reviewer_note: Mapped[str | None] = mapped_column(Text)

    # Verified Auth0 identity of the reviewer who last approved, modified, or
    # rejected this action. Null on PENDING rows and on records created before
    # authentication existed — never backfilled with guessed names.
    reviewed_by_sub: Mapped[str | None] = mapped_column(String(128))
    reviewed_by_email: Mapped[str | None] = mapped_column(String(255))
    reviewed_by_name: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    customer: Mapped["Customer"] = relationship(back_populates="actions")  # noqa: F821

    # =========================================================
    # 3. TRANSITION RULES
    # =========================================================

    def can_transition_to(self, new_status: str) -> bool:
        """True when the review workflow permits this status change."""
        return new_status in ALLOWED_TRANSITIONS.get(self.status, frozenset())

    @property
    def is_decided(self) -> bool:
        """True once the action has reached a terminal state."""
        return not ALLOWED_TRANSITIONS.get(self.status, frozenset())
