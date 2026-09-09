"""Prediction table — an append-only history of churn scores.

Predictions are inserted, never updated. A retention decision made last week was
based on last week's score, so overwriting it would destroy the audit trail that
makes an approved action defensible.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Prediction(Base):
    """One churn prediction produced by the trained model for one customer."""

    __tablename__ = "predictions"
    __table_args__ = (
        # The common read is "latest prediction for this customer" (max id).
        Index("ix_predictions_customer_created", "customer_id", "created_at"),
        Index("ix_predictions_customer_id", "customer_id", "id"),
        CheckConstraint(
            "risk_level IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_predictions_risk_level",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False
    )

    churn_probability: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)

    # Recorded per row so a score can always be traced to the artifact that
    # produced it, even after the model is retrained.
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    customer: Mapped["Customer"] = relationship(back_populates="predictions")  # noqa: F821
