"""Transparent ranking of what-if scenarios.

# =========================================================
# 1. WHY NOT SIMPLY PICK THE LOWEST PROBABILITY
# =========================================================

"Whichever hypothetical profile the model scores lowest" is a bad rule. It would
happily recommend flipping a feature that is currently *protecting* the customer,
or a play the customer's actual risk evidence gives no support for, purely
because the model's linear score moves. The model's response is one signal among
several, and it is the one most vulnerable to being an artefact.

# =========================================================
# 2. THE SCORE
# =========================================================

    ranking_score = 0.50 * model_response
                  + 0.30 * evidence_alignment
                  + 0.20 * driver_targeting

    if the scenario conflicts with the evidence:
        ranking_score *= 0.50

Each factor lies in [0, 1] and is reported on the outcome, so a reviewer can
recompute the score by hand:

* **model_response** — relative fall in the model's estimate,
  ``max(0, baseline - scenario) / baseline``. A scenario that raises the estimate
  scores zero rather than negative; it is simply not a candidate.
* **evidence_alignment** — the Step 4 strategy engine's alignment score for this
  scenario's strategy, i.e. the share of the customer's risk-increasing SHAP
  impact that strategy addresses. Zero when the strategy is not among the
  customer's eligible candidates, which is how an ineligible play (a contract
  conversion for a two-year customer) is kept out of the ranking.
* **driver_targeting** — the share of risk-increasing SHAP impact carried by the
  features this scenario actually changes. Distinguishes a scenario that touches
  the customer's real problem from one that happens to move the score.

The weights encode a deliberate stance: the model's response matters most, but
alone it can never exceed 0.50 and so cannot outrank a scenario that is both
responsive and evidence-aligned.

# =========================================================
# 3. THE CONFLICT PENALTY
# =========================================================

A scenario "conflicts with the evidence" when it changes a feature that is
currently *lowering* this customer's risk estimate. Acting against a protective
factor may still move the number, but proposing it as a retention play needs a
human to think, so the score is halved and the reason is recorded.
"""

from __future__ import annotations

from agent.models.evidence import CustomerEvidence
from agent.models.strategy import StrategyEvaluation
from agent.models.whatif import RankingFactors
from agent.simulation.simulator import ScenarioSimulation

FACTOR_WEIGHTS: dict[str, float] = {
    "model_response": 0.50,
    "evidence_alignment": 0.30,
    "driver_targeting": 0.20,
}

CONFLICT_PENALTY = 0.50

RANKING_METHODOLOGY = (
    "ranking_score = 0.50 * model_response + 0.30 * evidence_alignment "
    "+ 0.20 * driver_targeting, halved when the scenario changes a feature that "
    "currently lowers the customer's risk estimate. model_response is the relative "
    "fall in the model's probability estimate; evidence_alignment is the strategy "
    "engine's SHAP alignment score for the scenario's strategy; driver_targeting is "
    "the share of risk-increasing SHAP impact carried by the changed features."
)


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


# =========================================================
# 4. INDIVIDUAL FACTORS
# =========================================================


def compute_model_response(baseline_probability: float, scenario_probability: float) -> float:
    """Relative fall in the model's estimate; zero if the estimate does not fall."""
    if baseline_probability <= 0:
        return 0.0
    improvement = baseline_probability - scenario_probability
    if improvement <= 0:
        return 0.0
    return _clamp(improvement / baseline_probability)


def compute_evidence_alignment(strategy_id: str, evaluation: StrategyEvaluation) -> float:
    """The Step 4 alignment score for this scenario's strategy.

    Zero when the strategy is not an eligible candidate for the customer, which
    keeps contraindicated plays out of the recommendation.
    """
    for candidate in evaluation.candidates:
        if candidate.strategy_id == strategy_id:
            return _clamp(candidate.alignment_score)
    return 0.0


def compute_driver_targeting(
    changed_features: tuple[str, ...], evidence: CustomerEvidence
) -> float:
    """Share of risk-increasing SHAP impact carried by the changed features."""
    changed = set(changed_features)
    return _clamp(
        sum(driver.impact for driver in evidence.risk_increasing_drivers if driver.feature in changed)
    )


def detect_evidence_conflict(
    changed_features: tuple[str, ...], evidence: CustomerEvidence
) -> str | None:
    """Return why a scenario works against the customer's evidence, or None."""
    changed = set(changed_features)
    protective = [
        driver.feature for driver in evidence.protective_drivers if driver.feature in changed
    ]
    if not protective:
        return None
    return (
        f"the scenario changes {', '.join(protective)}, which currently lower(s) this "
        "customer's churn probability estimate."
    )


# =========================================================
# 5. COMBINED SCORE
# =========================================================


def score_scenario(
    simulation: ScenarioSimulation,
    evidence: CustomerEvidence,
    evaluation: StrategyEvaluation,
) -> tuple[float, RankingFactors, str | None]:
    """Score one simulated scenario.

    Returns:
        ``(ranking_score, factors, conflict_reason)`` — the factors and the
        conflict reason are carried on the outcome so the score is reproducible
        by hand.
    """
    changed_features = simulation.scenario.changed_feature_names

    model_response = compute_model_response(
        simulation.baseline_probability, simulation.scenario_probability
    )
    evidence_alignment = compute_evidence_alignment(simulation.scenario.strategy_id, evaluation)
    driver_targeting = compute_driver_targeting(changed_features, evidence)
    conflict_reason = detect_evidence_conflict(changed_features, evidence)

    score = (
        FACTOR_WEIGHTS["model_response"] * model_response
        + FACTOR_WEIGHTS["evidence_alignment"] * evidence_alignment
        + FACTOR_WEIGHTS["driver_targeting"] * driver_targeting
    )
    if conflict_reason is not None:
        score *= CONFLICT_PENALTY

    factors = RankingFactors(
        model_response=round(model_response, 4),
        evidence_alignment=round(evidence_alignment, 4),
        driver_targeting=round(driver_targeting, 4),
        conflict_penalty_applied=conflict_reason is not None,
    )
    return round(_clamp(score), 4), factors, conflict_reason
