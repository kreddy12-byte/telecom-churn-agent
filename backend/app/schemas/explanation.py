"""SHAP explanation contract.

This mirrors the Step 3 output exactly, including ``explained_output`` and
``base_value``. Those two fields are what make the numbers interpretable: SHAP
values here are contributions to the model's **log-odds**, not to a probability,
because only the log-odds decomposition is additive for logistic regression.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.prediction import RiskDriver


class ExplanationResponse(BaseModel):
    """Per-customer explanation produced by the trained model's SHAP explainer."""

    customer_id: str
    churn_probability: float = Field(..., ge=0.0, le=1.0)
    prediction: int = Field(..., ge=0, le=1)
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    model_version: str

    explained_output: Literal["log_odds"] = Field(
        ...,
        description=(
            "The model output SHAP values explain. Fixed to log_odds: "
            "base_value + sum(all SHAP values) equals the model's log-odds exactly."
        ),
    )
    base_value: float = Field(
        ..., description="Average model log-odds over the SHAP background sample."
    )
    top_drivers: list[RiskDriver] = Field(
        default_factory=list, description="Drivers ranked by absolute contribution."
    )


class GlobalDriver(BaseModel):
    """One original feature from the stored global SHAP importance artifact."""

    feature: str
    mean_absolute_shap: float
    mean_signed_shap: float


class GlobalImportanceResponse(BaseModel):
    """Read-only view of ``global_feature_importance.csv``. SHAP is not recomputed."""

    drivers: list[GlobalDriver]
    explained_output: Literal["log_odds"] = "log_odds"
