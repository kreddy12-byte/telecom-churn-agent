"""Read-only aggregates for the reviewer overview.

Every count is derived from stored rows. Nothing here is estimated or invented.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.customer import CustomerSummary


class OverviewResponse(BaseModel):
    """Population and review counts taken from PostgreSQL (or the local DB)."""

    customer_count: int = Field(..., ge=0)
    evaluated_count: int = Field(
        ...,
        ge=0,
        description="Distinct customers with at least one stored prediction.",
    )
    risk_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Latest stored prediction per customer, grouped by risk band.",
    )
    action_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Human-review actions grouped by status.",
    )
    recent_high_risk: list[CustomerSummary] = Field(default_factory=list)
