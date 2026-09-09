"""Retention strategy definitions and evaluation results."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agent.models.evidence import DriverEvidence


class RetentionStrategy(BaseModel):
    """A business-approved retention play.

    Strategies are *data*, not code branches, so a reviewer (or a business
    stakeholder) can read the catalogue and understand exactly what the system
    is allowed to propose. The LLM may only choose from these; it can never
    invent a new play.
    """

    model_config = ConfigDict(frozen=True)

    strategy_id: str
    name: str
    description: str
    objective: str

    # Features whose SHAP evidence makes this strategy relevant.
    applicable_risk_drivers: tuple[str, ...] = ()

    # What a human agent is permitted to do under this strategy.
    allowed_actions: tuple[str, ...] = ()

    # Human-readable reasons this strategy may be inappropriate.
    contraindications: tuple[str, ...] = ()

    # Business preference used only to break scoring ties (1 = preferred).
    priority: int = 5

    # ----------------------------------------------------------------- #
    # Declarative eligibility guards — kept as data so the rules are
    # auditable instead of buried in conditionals.
    # ----------------------------------------------------------------- #

    # Strategy only applies when tenure is at or below this many months.
    max_tenure_months: int | None = None

    # Profile values that rule the strategy out, e.g. {"Contract": ("Two year",)}
    # means "do not propose a contract conversion to someone already on the
    # longest contract".
    excluded_profile_values: dict[str, tuple[str, ...]] = Field(default_factory=dict)

    # The catalogue-wide fallback used when nothing else applies.
    is_fallback: bool = False


class StrategyCandidate(BaseModel):
    """A strategy that survived eligibility checks, with its evidence score."""

    model_config = ConfigDict(frozen=True)

    strategy: RetentionStrategy
    alignment_score: float = Field(
        ...,
        ge=0.0,
        description="Sum of the normalised SHAP impact of matched risk-increasing drivers.",
    )
    matched_drivers: tuple[DriverEvidence, ...] = ()
    rationale: str = ""

    @property
    def strategy_id(self) -> str:
        return self.strategy.strategy_id


class StrategyEvaluation(BaseModel):
    """Full outcome of evaluating one customer against the catalogue."""

    model_config = ConfigDict(frozen=True)

    candidates: tuple[StrategyCandidate, ...]
    rejected: tuple[tuple[str, str], ...] = ()  # (strategy_id, reason)

    @property
    def best(self) -> StrategyCandidate:
        """Highest-ranked candidate; the evaluator guarantees at least one."""
        return self.candidates[0]

    @property
    def candidate_ids(self) -> list[str]:
        return [candidate.strategy_id for candidate in self.candidates]

    @property
    def score_margin(self) -> float:
        """Gap between the best and second-best candidate.

        A small margin means the evidence does not clearly favour one play,
        which the confidence model treats as ambiguity.
        """
        if len(self.candidates) < 2:
            return self.candidates[0].alignment_score if self.candidates else 0.0
        return self.candidates[0].alignment_score - self.candidates[1].alignment_score
