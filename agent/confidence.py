"""Deterministic confidence scoring.

Why the system computes confidence instead of asking the LLM
------------------------------------------------------------
A language model asked "how confident are you?" will answer fluently and
meaninglessly — it has no access to how decisive the prediction was or how
cleanly the evidence pointed at one play. Confidence here is therefore computed
from measurable properties of the prediction and the strategy evaluation. The
LLM may *lower* the result (if it flags uncertainty) but can never raise it.

The four factors
----------------
1. **Prediction decisiveness** — how far the churn probability sits from the 0.5
   decision boundary. A 0.87 prediction is a firmer basis for action than 0.52.
2. **Evidence alignment** — what share of the customer's total SHAP movement the
   selected strategy actually addresses. Acting on 5% of the evidence is weak.
3. **Actionable support** — how many risk-increasing drivers the strategy
   matched. One driver is thinner evidence than several agreeing ones.
4. **Discrimination** — how far ahead the winner is from the runner-up. When two
   plays score almost identically, the choice between them is close to arbitrary
   and confidence should reflect that.

Hard caps are applied afterwards so that no arithmetic can produce an
indefensible "HIGH".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.models.evidence import CustomerEvidence
from agent.models.recommendation import ConfidenceLevel
from agent.models.strategy import StrategyCandidate, StrategyEvaluation

# Weights sum to 1.0. Decisiveness and alignment dominate because they measure
# whether there is a real, targetable problem; the others temper over-claiming.
FACTOR_WEIGHTS: dict[str, float] = {
    "prediction_decisiveness": 0.30,
    "evidence_alignment": 0.30,
    "actionable_support": 0.20,
    "discrimination": 0.20,
}

HIGH_THRESHOLD = 0.65
MEDIUM_THRESHOLD = 0.40

# A probability this far from 0.5 counts as fully decisive.
DECISIVENESS_SATURATION = 0.35

# Matching this many risk-increasing drivers counts as full support.
FULL_SUPPORT_DRIVER_COUNT = 2

CONFIDENCE_ORDER: dict[ConfidenceLevel, int] = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


@dataclass(frozen=True)
class ConfidenceAssessment:
    """Computed confidence plus the factors that produced it."""

    level: ConfidenceLevel
    score: float
    rationale: str
    factors: dict[str, float] = field(default_factory=dict)


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


# =========================================================
# 1. MEASURE THE INDIVIDUAL FACTORS
# =========================================================


def _prediction_decisiveness(churn_probability: float) -> float:
    """Distance from the 0.5 decision boundary, saturating at ±0.35."""
    return _clamp(abs(churn_probability - 0.5) / DECISIVENESS_SATURATION)


def _evidence_alignment(chosen: StrategyCandidate) -> float:
    """Share of the customer's SHAP movement addressed by the chosen strategy."""
    return _clamp(chosen.alignment_score)


def _actionable_support(chosen: StrategyCandidate) -> float:
    """How many matched risk-increasing drivers back the chosen strategy."""
    return _clamp(len(chosen.matched_drivers) / FULL_SUPPORT_DRIVER_COUNT)


def _discrimination(evaluation: StrategyEvaluation, chosen: StrategyCandidate) -> float:
    """How clearly the chosen strategy beats the best alternative.

    Computed against whichever strategy was actually selected, which may not be
    the top-ranked one: if the AI reasoning layer overrides the engine's ranking,
    the margin goes to zero and confidence drops accordingly.
    """
    if chosen.alignment_score <= 0:
        return 0.0

    alternative_scores = [
        candidate.alignment_score
        for candidate in evaluation.candidates
        if candidate.strategy_id != chosen.strategy_id
    ]
    best_alternative = max(alternative_scores, default=0.0)
    margin = chosen.alignment_score - best_alternative
    return _clamp(margin / chosen.alignment_score)


# =========================================================
# 2. COMBINE, BAND, AND CAP
# =========================================================


def _band(score: float) -> ConfidenceLevel:
    if score >= HIGH_THRESHOLD:
        return "HIGH"
    if score >= MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def assess_confidence(
    evidence: CustomerEvidence,
    evaluation: StrategyEvaluation,
    selected: StrategyCandidate | None = None,
) -> ConfidenceAssessment:
    """Compute a defensible confidence level for the selected strategy.

    Args:
        evidence: The customer's ML/SHAP evidence.
        evaluation: Full strategy evaluation.
        selected: The strategy actually chosen. Defaults to the engine's
            top-ranked candidate; differs when the AI layer picks another.
    """
    chosen = selected or evaluation.best

    factors = {
        "prediction_decisiveness": round(_prediction_decisiveness(evidence.churn_probability), 4),
        "evidence_alignment": round(_evidence_alignment(chosen), 4),
        "actionable_support": round(_actionable_support(chosen), 4),
        "discrimination": round(_discrimination(evaluation, chosen), 4),
    }

    weighted_score = sum(FACTOR_WEIGHTS[name] * value for name, value in factors.items())
    level = _band(weighted_score)
    caps: list[str] = []

    # --- Hard caps: situations where a high claim is never defensible --- #

    if chosen.strategy.is_fallback:
        # "Escalate to a human because we could not identify a play" is by
        # definition not a confident recommendation.
        level = "LOW"
        caps.append("the selected play is the escalation fallback")

    if not evidence.risk_increasing_drivers:
        level = "LOW"
        caps.append("no risk-increasing drivers were present in the evidence")

    if evidence.risk_level == "LOW" and CONFIDENCE_ORDER[level] > CONFIDENCE_ORDER["MEDIUM"]:
        # Intervening on a low-risk customer is speculative regardless of how
        # tidy the evidence looks.
        level = "MEDIUM"
        caps.append("the customer is in the LOW risk band")

    rationale = (
        f"Weighted confidence score {weighted_score:.2f} from "
        f"decisiveness {factors['prediction_decisiveness']:.2f}, "
        f"evidence alignment {factors['evidence_alignment']:.2f}, "
        f"driver support {factors['actionable_support']:.2f}, "
        f"strategy discrimination {factors['discrimination']:.2f}."
    )
    if caps:
        rationale += " Capped because " + " and ".join(caps) + "."

    return ConfidenceAssessment(
        level=level,
        score=round(weighted_score, 4),
        rationale=rationale,
        factors=factors,
    )


def downgrade_only(
    computed: ConfidenceLevel, claimed: ConfidenceLevel | None
) -> ConfidenceLevel:
    """Let an LLM lower confidence but never raise it.

    If the model spots a reason for caution we want to hear it; if it simply
    asserts "HIGH", we ignore it.
    """
    if claimed is None or claimed not in CONFIDENCE_ORDER:
        return computed
    return claimed if CONFIDENCE_ORDER[claimed] < CONFIDENCE_ORDER[computed] else computed
