"""The final recommendation contract produced by the agent."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent.models.evidence import Direction, RiskLevel

ConfidenceLevel = Literal["LOW", "MEDIUM", "HIGH"]

# Provider label used when no LLM produced the text. Callers can rely on this
# exact value to tell machine-written prose from template-generated prose.
PROVIDER_DETERMINISTIC = "deterministic_fallback"

# Attached to every recommendation. These are properties of the method, not of
# an individual customer, so they are owned by the system rather than the LLM.
STANDARD_LIMITATIONS: tuple[str, ...] = (
    "SHAP values describe how the model reached its prediction and do not establish causality.",
    "This is decision support only; a human must review and approve any customer contact.",
    "The recommendation reflects the data supplied to the model and may be wrong for this customer.",
)


class SelectedStrategy(BaseModel):
    """The retention play chosen for this customer."""

    model_config = ConfigDict(frozen=True)

    strategy_id: str
    strategy_name: str


class SupportingEvidence(BaseModel):
    """A model-derived fact backing the recommendation.

    Always populated by the system from real SHAP output — never by the LLM —
    so the numbers in a recommendation cannot be fabricated.
    """

    model_config = ConfigDict(frozen=True)

    feature: str
    value: Any = None
    shap_value: float
    direction: Direction


class RetentionRecommendation(BaseModel):
    """Structured, human-approvable retention recommendation."""

    model_config = ConfigDict(extra="forbid")

    # --- Prediction (from the ML model) ---
    customer_id: str | None = None
    churn_probability: float = Field(..., ge=0.0, le=1.0)
    risk_level: RiskLevel
    model_version: str = "unknown"

    # --- Selected play (from the strategy engine, validated against the catalogue) ---
    selected_strategy: SelectedStrategy

    # --- Reasoning and recommendation (LLM prose or deterministic template) ---
    recommendation: str = Field(..., min_length=1)
    reasoning: list[str] = Field(default_factory=list)

    # --- Evidence (always system-owned) ---
    supporting_evidence: list[SupportingEvidence] = Field(default_factory=list)

    # --- Intent, trust, and governance ---
    objective: str
    confidence: ConfidenceLevel
    confidence_rationale: str = ""
    requires_human_approval: bool = True
    limitations: list[str] = Field(default_factory=lambda: list(STANDARD_LIMITATIONS))

    # --- Provenance ---
    provider: str = PROVIDER_DETERMINISTIC
    fallback_reason: str | None = None
    candidate_strategy_ids: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("requires_human_approval")
    @classmethod
    def _approval_is_mandatory(cls, value: bool) -> bool:
        """The agent is decision support; it can never self-authorise an action.

        Enforced in the schema so no code path — including a compromised or
        confused LLM response — can produce an auto-approved recommendation.
        """
        if value is not True:
            raise ValueError("requires_human_approval must always be True.")
        return True

    @property
    def generated_by_llm(self) -> bool:
        return self.provider != PROVIDER_DETERMINISTIC

    def to_api_contract(self) -> dict[str, Any]:
        """Project onto the ``RecommendationResponse`` schema defined in Step 1.

        The backend endpoint (Step 5) will use this, which is why the mapping
        lives with the model rather than inside the future route.
        """
        return {
            "customer_id": self.customer_id or "",
            "recommendation": self.recommendation,
            "reason": " ".join(self.reasoning) if self.reasoning else self.objective,
            "priority": self.risk_level,
            "confidence": self.confidence,
            "requires_human_approval": True,
        }
