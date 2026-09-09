"""Safe subset of the trained model's metadata for reviewer transparency.

Absolute filesystem paths, environment fingerprints, and secrets are omitted.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelInfoResponse(BaseModel):
    """Public facts about the locked Step 2/3 artifacts."""

    model_name: str
    model_version: str
    target: str
    dataset_name: str
    dataset_rows_used: int | None = None
    feature_count: int
    transformed_feature_count: int | None = None
    explainability: str = "SHAP LinearExplainer"
    explained_output: str = "log_odds"
    training_date: str | None = None
    risk_thresholds: dict[str, float] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    class_balance: dict[str, Any] = Field(default_factory=dict)
    selection_reason: str | None = None
