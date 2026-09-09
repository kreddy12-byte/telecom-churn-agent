"""Multi-scenario comparison: the strategy comparison engine.

# =========================================================
# 1. THE FLOW
# =========================================================

    customer record
        -> baseline prediction + SHAP        (Step 2 / Step 3)
        -> customer evidence                 (Step 4 contract)
        -> eligible retention strategies     (Step 4 engine)
        -> every applicable what-if scenario (Step 5 simulator)
        -> transparent ranking               (Step 5 ranking)
        -> AI interpretation                 (Step 4 provider abstraction)
        -> human approval

The system computes every number. The AI, if configured, only reads the results
back in prose.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from agent.models.evidence import CustomerEvidence
from agent.models.scenario import Scenario
from agent.models.strategy import StrategyEvaluation
from agent.models.whatif import (
    ScenarioOutcome,
    ScenarioRejection,
    WhatIfResult,
    WHATIF_LIMITATIONS,
)
from agent.services.evidence_builder import sanitise_profile
from agent.simulation.catalogue import get_scenario_catalogue, unsimulatable_for_strategies
from agent.simulation.ranking import RANKING_METHODOLOGY, score_scenario
from agent.simulation.simulator import TOP_DRIVER_DISPLAY_COUNT, ScenarioSimulation, WhatIfSimulator
from agent.simulation.validator import ScenarioValidationError
from agent.strategies.evaluator import evaluate_customer
from ml.src.logging_config import get_logger

logger = get_logger(__name__)

# Drivers handed to the Step 4 strategy engine. Matches the agent's default so
# candidate scores are identical to those the recommendation service reports.
STRATEGY_EVIDENCE_DRIVER_COUNT = 10


# =========================================================
# 2. BUILD EVIDENCE FROM THE BASELINE EXPLANATION
# =========================================================


def _evidence_from_baseline(
    explanation: dict[str, Any], profile: Mapping[str, Any], driver_count: int
) -> CustomerEvidence:
    """Reuse the baseline explanation as Step 4 customer evidence.

    The simulator explains every feature so scenarios can be compared, but the
    strategy engine is given the same top-N slice it always receives, so its
    candidate scores stay consistent with the recommendation service.
    """
    truncated = dict(explanation)
    truncated["top_drivers"] = explanation["top_drivers"][:driver_count]
    return CustomerEvidence.from_explanation(truncated, customer_profile=sanitise_profile(profile))


# =========================================================
# 3. TURN A SIMULATION INTO A RANKED OUTCOME
# =========================================================


def _build_outcome(
    simulation: ScenarioSimulation,
    evidence: CustomerEvidence,
    evaluation: StrategyEvaluation,
) -> ScenarioOutcome:
    """Attach ranking and limitations to a raw simulation."""
    ranking_score, factors, conflict_reason = score_scenario(simulation, evidence, evaluation)
    scenario = simulation.scenario

    limitations = list(WHATIF_LIMITATIONS)
    limitations.extend(scenario.limitations)
    if conflict_reason is not None:
        limitations.append(f"Evidence conflict: {conflict_reason}")

    return ScenarioOutcome(
        scenario_id=scenario.scenario_id,
        scenario_name=scenario.scenario_name,
        strategy_id=scenario.strategy_id,
        description=scenario.description,
        rationale=scenario.rationale,
        changed_features=dict(scenario.changed_features),
        baseline_probability=round(simulation.baseline_probability, 4),
        scenario_probability=round(simulation.scenario_probability, 4),
        absolute_probability_change=simulation.absolute_change,
        relative_probability_change=simulation.relative_change,
        percentage_point_change=round(simulation.absolute_change * 100, 2),
        baseline_risk_level=simulation.baseline_risk_level,
        scenario_risk_level=simulation.scenario_risk_level,
        risk_level_changed=simulation.baseline_risk_level != simulation.scenario_risk_level,
        baseline_top_drivers=simulation.baseline_drivers[:TOP_DRIVER_DISPLAY_COUNT],
        scenario_top_drivers=simulation.scenario_drivers[:TOP_DRIVER_DISPLAY_COUNT],
        driver_deltas=simulation.driver_deltas[:TOP_DRIVER_DISPLAY_COUNT],
        ranking_score=ranking_score,
        ranking_factors=factors,
        conflicts_with_evidence=conflict_reason is not None,
        conflict_reason=conflict_reason,
        model_based_interpretation=simulation.interpretation,
        limitations=limitations,
    )


# =========================================================
# 4. SELECT A RECOMMENDED SCENARIO
# =========================================================


def select_recommended_scenario(
    outcomes: Sequence[ScenarioOutcome],
) -> tuple[str | None, str]:
    """Pick the highest-ranked scenario worth putting in front of a human.

    A scenario qualifies only if the model's estimate actually falls under it and
    it does not work against a protective driver. When nothing qualifies the
    honest answer is "none", not the least-bad option.
    """
    eligible = [
        outcome
        for outcome in outcomes
        if outcome.model_estimate_improved and not outcome.conflicts_with_evidence
    ]

    if not eligible:
        if not outcomes:
            return None, "No scenario in the catalogue applies to this customer's profile."
        return None, (
            "No scenario lowered the model's churn probability estimate without working "
            "against a driver that currently reduces this customer's risk, so no scenario "
            "is put forward."
        )

    # Ties break on scenario id so the choice is reproducible regardless of the
    # order the caller supplied.
    best = min(eligible, key=lambda outcome: (-outcome.ranking_score, outcome.scenario_id))
    factors = best.ranking_factors
    reason = (
        f"'{best.scenario_name}' ranks highest with a score of {best.ranking_score:.4f}. "
        f"The model's estimate moves from {best.baseline_probability:.2%} to "
        f"{best.scenario_probability:.2%} ({best.percentage_point_change:+.2f} percentage "
        f"points, model_response {factors.model_response:.2f}); its strategy "
        f"{best.strategy_id} addresses {factors.evidence_alignment:.2f} of the customer's "
        f"risk-increasing SHAP impact; and the features it changes carry "
        f"{factors.driver_targeting:.2f} of that impact."
    )
    return best.scenario_id, reason


# =========================================================
# 5. THE COMPARISON ENGINE
# =========================================================


def compare_retention_scenarios(
    customer_data: Mapping[str, Any],
    scenarios: Sequence[Scenario] | None = None,
    models_dir: Path | str | None = None,
) -> WhatIfResult:
    """Evaluate every applicable scenario for one customer and rank the results.

    Args:
        customer_data: The customer's real record.
        scenarios: Scenarios to evaluate; defaults to the approved catalogue.
        models_dir: Override for the model artifact directory (used by tests).

    Invalid or inapplicable scenarios are reported in ``rejected_scenarios``
    rather than aborting the comparison, because one bad scenario must not cost
    the reviewer every other result.
    """
    simulator = WhatIfSimulator(models_dir=models_dir)
    candidate_scenarios = tuple(scenarios) if scenarios is not None else get_scenario_catalogue()

    # --- 1. BASELINE --- #
    baseline, baseline_explanation = simulator.baseline(customer_data)

    # --- 2. EVIDENCE AND ELIGIBLE STRATEGIES (reused from Step 4) --- #
    evidence = _evidence_from_baseline(
        baseline_explanation, customer_data, STRATEGY_EVIDENCE_DRIVER_COUNT
    )
    evaluation = evaluate_customer(evidence)

    # --- 3. EVALUATE EACH SCENARIO --- #
    outcomes: list[ScenarioOutcome] = []
    rejections: list[ScenarioRejection] = []

    for scenario in candidate_scenarios:
        try:
            simulation = simulator.simulate(scenario, customer_data, baseline_explanation)
        except ScenarioValidationError as exc:
            logger.info("Skipping scenario '%s': %s", scenario.scenario_id, exc.reason)
            rejections.append(
                ScenarioRejection(
                    scenario_id=scenario.scenario_id,
                    scenario_name=scenario.scenario_name,
                    reason=exc.reason,
                )
            )
            continue
        outcomes.append(_build_outcome(simulation, evidence, evaluation))

    # --- 4. RANK --- #
    outcomes.sort(key=lambda outcome: (-outcome.ranking_score, outcome.scenario_id))
    recommended_id, selection_reason = select_recommended_scenario(outcomes)

    # --- 5. REPORT WHAT CANNOT BE SIMULATED AT ALL --- #
    unsimulatable = unsimulatable_for_strategies(set(evaluation.candidate_ids))

    return WhatIfResult(
        customer_id=evidence.customer_id,
        customer_profile=evidence.customer_profile,
        baseline=baseline,
        candidate_strategy_ids=evaluation.candidate_ids,
        scenarios=outcomes,
        rejected_scenarios=rejections,
        unsimulatable_interventions=list(unsimulatable),
        recommended_scenario_id=recommended_id,
        selection_reason=selection_reason,
        ranking_methodology=RANKING_METHODOLOGY,
        requires_human_approval=True,
    )
