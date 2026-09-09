"""Customer request/response contracts.

Field names follow the database's snake_case rather than the dataset's original
casing: these schemas describe the API, and the dataset's naming is an ML
implementation detail that the API consumer should not have to know.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PageMeta


class LatestPrediction(BaseModel):
    """The most recent stored score for a customer, if one exists."""

    model_config = ConfigDict(from_attributes=True)

    churn_probability: float = Field(..., ge=0.0, le=1.0)
    risk_level: str
    model_version: str
    created_at: datetime


class LatestAction(BaseModel):
    """The most recent human-review action for a customer, if one exists."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    strategy_id: str
    updated_at: datetime


class CustomerSummary(BaseModel):
    """Lightweight customer view for list responses."""

    model_config = ConfigDict(from_attributes=True)

    customer_id: str
    tenure: int | None = None
    contract: str | None = None
    monthly_charges: float | None = None
    internet_service: str | None = None

    # Read from the predictions / actions tables, never computed on the fly.
    latest_prediction: LatestPrediction | None = None
    latest_action: LatestAction | None = None


class CustomerDetail(CustomerSummary):
    """Full customer profile — every feature the churn model consumes."""

    gender: str | None = None
    senior_citizen: int | None = None
    partner: str | None = None
    dependents: str | None = None
    phone_service: str | None = None
    multiple_lines: str | None = None
    online_security: str | None = None
    online_backup: str | None = None
    device_protection: str | None = None
    tech_support: str | None = None
    streaming_tv: str | None = None
    streaming_movies: str | None = None
    paperless_billing: str | None = None
    payment_method: str | None = None
    total_charges: float | None = None
    created_at: datetime
    updated_at: datetime


class CustomerListResponse(BaseModel):
    """A page of customers plus the metadata needed to request the next one."""

    items: list[CustomerSummary]
    meta: PageMeta
