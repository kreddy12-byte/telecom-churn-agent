"""Evidence the agent reasons over.

This is the contract between the ML/SHAP layers and the agent. It mirrors the
output of ``ml.src.explainability.explain_customer`` exactly, so the agent never
re-derives model facts — it only consumes them.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]
Direction = Literal["increases_risk", "decreases_risk"]

DIRECTION_INCREASES = "increases_risk"


class DriverEvidence(BaseModel):
    """One SHAP driver: a feature and how it moved this customer's prediction."""

    model_config = ConfigDict(extra="ignore")

    feature: str = Field(..., min_length=1)
    value: Any = None
    impact: float = Field(..., ge=0.0, le=1.0, description="Share of total absolute SHAP impact.")
    direction: Direction
    shap_value: float = Field(..., description="Signed contribution to churn log-odds.")

    @property
    def increases_risk(self) -> bool:
        return self.direction == DIRECTION_INCREASES


class CustomerEvidence(BaseModel):
    """Everything the agent is allowed to know about a customer.

    The agent may reason *only* over these fields. Anything not present here is,
    by definition, a fact the agent must not assert.
    """

    model_config = ConfigDict(extra="forbid")

    customer_id: str | None = None
    churn_probability: float = Field(..., ge=0.0, le=1.0)
    risk_level: RiskLevel
    prediction: int = Field(..., ge=0, le=1)
    model_version: str = "unknown"
    explained_output: str = "log_odds"
    top_drivers: list[DriverEvidence] = Field(default_factory=list)
    customer_profile: dict[str, Any] = Field(default_factory=dict)

    @field_validator("top_drivers")
    @classmethod
    def _reject_duplicate_features(cls, drivers: list[DriverEvidence]) -> list[DriverEvidence]:
        """Duplicated features would double-count a driver during scoring."""
        features = [driver.feature for driver in drivers]
        if len(features) != len(set(features)):
            raise ValueError("top_drivers contains duplicate features.")
        return drivers

    # ----------------------------------------------------------------- #
    # Convenience accessors used by the strategy engine
    # ----------------------------------------------------------------- #

    @property
    def risk_increasing_drivers(self) -> list[DriverEvidence]:
        """Drivers pushing this customer toward churn — the actionable ones."""
        return [driver for driver in self.top_drivers if driver.increases_risk]

    @property
    def protective_drivers(self) -> list[DriverEvidence]:
        """Drivers reducing churn risk; useful context, not intervention targets."""
        return [driver for driver in self.top_drivers if not driver.increases_risk]

    def driver_for(self, feature: str) -> DriverEvidence | None:
        """Return the driver for ``feature`` if the explanation included it."""
        for driver in self.top_drivers:
            if driver.feature == feature:
                return driver
        return None

    def profile_value(self, feature: str) -> Any:
        """Read a raw customer attribute; returns None when it was not supplied.

        Used so generated text can quote real values instead of inventing them.
        """
        return self.customer_profile.get(feature)

    @classmethod
    def from_explanation(
        cls,
        explanation: dict[str, Any],
        customer_profile: dict[str, Any] | None = None,
    ) -> CustomerEvidence:
        """Build evidence from ``explain_customer`` output.

        Keeping this conversion in one place means a change to the SHAP contract
        breaks loudly here rather than silently degrading recommendations.
        """
        required_keys = {"churn_probability", "risk_level", "prediction", "top_drivers"}
        missing = sorted(required_keys - set(explanation))
        if missing:
            raise ValueError(f"Explanation is missing required keys: {missing}")

        return cls(
            customer_id=explanation.get("customer_id"),
            churn_probability=explanation["churn_probability"],
            risk_level=explanation["risk_level"],
            prediction=explanation["prediction"],
            model_version=explanation.get("model_version", "unknown"),
            explained_output=explanation.get("explained_output", "log_odds"),
            top_drivers=[DriverEvidence(**driver) for driver in explanation["top_drivers"]],
            customer_profile=dict(customer_profile or {}),
        )
