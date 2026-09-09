"""Churn prediction contracts.

The response shape is the one agreed in Step 1 and produced by the ML layer in
Step 2. The backend re-publishes those numbers; it never computes them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import PageMeta


class RiskDriver(BaseModel):
    """A feature contributing to predicted churn risk.

    ``impact`` is the feature's share of the customer's total absolute SHAP
    contribution, so it is comparable across drivers and always in [0, 1].
    ``shap_value`` is the underlying signed contribution in log-odds.
    """

    feature: str
    value: Any = None
    impact: float = Field(..., ge=0.0, le=1.0)
    direction: Literal["increases_risk", "decreases_risk"]
    shap_value: float | None = None


class PredictionRequest(BaseModel):
    """Request body for ``POST /api/predict``."""

    customer_id: str = Field(..., min_length=1, examples=["7590-VHVEG"])


class PredictionResponse(BaseModel):
    """Shared prediction response contract."""

    customer_id: str
    churn_probability: float = Field(..., ge=0.0, le=1.0)
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    prediction: int = Field(..., ge=0, le=1, description="Predicted class at the 0.5 threshold.")
    model_version: str
    top_drivers: list[RiskDriver] = Field(default_factory=list)
    predicted_at: datetime | None = Field(
        default=None, description="When this prediction was recorded in the history table."
    )


class RiskCounts(BaseModel):
    """HIGH / MEDIUM / LOW counts from the latest prediction per customer."""

    HIGH: int = Field(0, ge=0)
    MEDIUM: int = Field(0, ge=0)
    LOW: int = Field(0, ge=0)


class BatchScoringResponse(BaseModel):
    """Result of scoring every stored customer with the production predictor."""

    processed: int = Field(..., ge=0, description="Customers loaded and sent to the predictor.")
    stored: int = Field(..., ge=0, description="Prediction-history rows appended this run.")
    model_version: str
    scored_at: datetime = Field(
        ...,
        description=(
            "Shared timestamp written onto every row in this run so the batch "
            "is identifiable without a schema change."
        ),
    )
    risk_counts: RiskCounts


class RankedPrediction(BaseModel):
    """One customer's latest stored score, for ranking views.

    Readable profile fields match the customer list. SHAP drivers and
    retention recommendations are intentionally absent.
    """

    customer_id: str
    tenure: int | None = None
    contract: str | None = None
    monthly_charges: float | None = None
    internet_service: str | None = None
    churn_probability: float = Field(..., ge=0.0, le=1.0)
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    model_version: str
    predicted_at: datetime


class PredictionRankingResponse(BaseModel):
    """A page of latest scores, highest churn probability first."""

    items: list[RankedPrediction]
    meta: PageMeta


class PredictionSummaryResponse(BaseModel):
    """Latest-per-customer distribution. Historical rows are not double-counted."""

    total_scored: int = Field(..., ge=0)
    risk_counts: RiskCounts
    average_churn_probability: float | None = Field(
        default=None, ge=0.0, le=1.0
    )
    highest_churn_probability: float | None = Field(
        default=None, ge=0.0, le=1.0
    )


class ProbabilityBucket(BaseModel):
    """One probability interval and how many latest scores fall in it."""

    bucket: str
    count: int = Field(..., ge=0)


class ProbabilityDistributionResponse(BaseModel):
    """Histogram of latest churn probabilities. Counts are not double-counted."""

    buckets: list[ProbabilityBucket]
    total_scored: int = Field(..., ge=0)
