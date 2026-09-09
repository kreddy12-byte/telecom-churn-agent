"""Scenario ranking and selection tests."""

from __future__ import annotations

import pytest

from agent.models.scenario import Scenario
from agent.simulation.comparison import select_recommended_scenario
from agent.simulation.ranking import (
    CONFLICT_PENALTY,
    FACTOR_WEIGHTS,
    compute_driver_targeting,
    compute_evidence_alignment,
    compute_model_response,
    detect_evidence_conflict,
    score_scenario,
)
from agent.simulation.simulator import ScenarioSimulation
from agent.strategies.evaluator import evaluate_customer
from agent.tests.conftest import make_scenario_outcome


def make_simulation(
    changed_features: dict,
    strategy_id: str = "CONTRACT_CONVERSION",
    baseline_probability: float = 0.80,
    scenario_probability: float = 0.60,
) -> ScenarioSimulation:
    """A simulation object with only the fields ranking depends on."""
    scenario = Scenario(
        scenario_id="test_scenario",
        scenario_name="Test Scenario",
        description="Test.",
        changed_features=changed_features,
        rationale="Test.",
        strategy_id=strategy_id,
    )
    return ScenarioSimulation(
        scenario=scenario,
        hypothetical_profile={},
        baseline_probability=baseline_probability,
        scenario_probability=scenario_probability,
        baseline_risk_level="HIGH",
        scenario_risk_level="MEDIUM",
        baseline_drivers=[],
        scenario_drivers=[],
        driver_deltas=[],
        interpretation="Test interpretation.",
    )


# =========================================================
# 1. INDIVIDUAL FACTORS
# =========================================================


def test_model_response_measures_relative_fall() -> None:
    assert compute_model_response(0.80, 0.60) == pytest.approx(0.25)


def test_model_response_is_zero_when_the_estimate_rises() -> None:
    """A scenario that makes things worse is not a candidate, not a negative one."""
    assert compute_model_response(0.60, 0.80) == 0.0


def test_model_response_handles_a_zero_baseline() -> None:
    assert compute_model_response(0.0, 0.0) == 0.0


def test_evidence_alignment_uses_the_strategy_engine(high_risk_evidence) -> None:
    evaluation = evaluate_customer(high_risk_evidence)

    assert compute_evidence_alignment("CONTRACT_CONVERSION", evaluation) == pytest.approx(0.15)
    assert compute_evidence_alignment("EARLY_LIFECYCLE_ONBOARDING", evaluation) == pytest.approx(0.35)


def test_evidence_alignment_is_zero_for_an_ineligible_strategy(low_risk_evidence) -> None:
    """Contract conversion is contraindicated for a two-year customer, so it scores nothing."""
    evaluation = evaluate_customer(low_risk_evidence)
    assert compute_evidence_alignment("CONTRACT_CONVERSION", evaluation) == 0.0


def test_driver_targeting_counts_only_risk_increasing_drivers(high_risk_evidence) -> None:
    assert compute_driver_targeting(("Contract",), high_risk_evidence) == pytest.approx(0.15)
    # InternetService currently lowers this customer's risk.
    assert compute_driver_targeting(("InternetService",), high_risk_evidence) == 0.0


def test_conflict_detection_flags_protective_features(high_risk_evidence) -> None:
    assert detect_evidence_conflict(("Contract",), high_risk_evidence) is None

    reason = detect_evidence_conflict(("InternetService",), high_risk_evidence)
    assert reason is not None and "InternetService" in reason


# =========================================================
# 2. COMBINED SCORE
# =========================================================


def test_score_is_reproducible_by_hand(high_risk_evidence) -> None:
    evaluation = evaluate_customer(high_risk_evidence)
    simulation = make_simulation({"Contract": "One year"})

    score, factors, conflict = score_scenario(simulation, high_risk_evidence, evaluation)

    expected = (
        FACTOR_WEIGHTS["model_response"] * 0.25
        + FACTOR_WEIGHTS["evidence_alignment"] * 0.15
        + FACTOR_WEIGHTS["driver_targeting"] * 0.15
    )
    assert score == pytest.approx(round(expected, 4))
    assert factors.model_response == pytest.approx(0.25)
    assert conflict is None


def test_conflicting_scenario_is_penalised(high_risk_evidence) -> None:
    evaluation = evaluate_customer(high_risk_evidence)
    clean = make_simulation({"Contract": "One year"})
    conflicting = make_simulation(
        {"Contract": "One year", "InternetService": "Fiber optic"},
    )

    clean_score, _, _ = score_scenario(clean, high_risk_evidence, evaluation)
    conflict_score, factors, reason = score_scenario(
        conflicting, high_risk_evidence, evaluation
    )

    assert reason is not None
    assert factors.conflict_penalty_applied is True
    assert conflict_score < clean_score
    assert conflict_score == pytest.approx(round(clean_score * CONFLICT_PENALTY, 4), abs=1e-4)


def test_score_stays_within_bounds(high_risk_evidence) -> None:
    evaluation = evaluate_customer(high_risk_evidence)
    extreme = make_simulation(
        {"Contract": "Two year"}, baseline_probability=0.99, scenario_probability=0.01
    )
    score, _, _ = score_scenario(extreme, high_risk_evidence, evaluation)

    assert 0.0 <= score <= 1.0


def test_a_scenario_that_moves_nothing_scores_only_on_evidence(high_risk_evidence) -> None:
    evaluation = evaluate_customer(high_risk_evidence)
    flat = make_simulation(
        {"Contract": "One year"}, baseline_probability=0.80, scenario_probability=0.80
    )
    score, factors, _ = score_scenario(flat, high_risk_evidence, evaluation)

    assert factors.model_response == 0.0
    assert score > 0  # evidence alignment and targeting still count


# =========================================================
# 3. SELECTION
# =========================================================


def test_selection_is_not_simply_the_lowest_probability() -> None:
    """The deepest drop loses when nothing else supports it."""
    weakly_supported = make_scenario_outcome("deep_drop", scenario_probability=0.30, ranking_score=0.10)
    well_supported = make_scenario_outcome("modest_drop", scenario_probability=0.60, ranking_score=0.50)

    chosen, reason = select_recommended_scenario([weakly_supported, well_supported])

    assert chosen == "modest_drop"
    assert "ranks highest" in reason


def test_conflicting_scenarios_are_never_recommended() -> None:
    conflicting = make_scenario_outcome(
        "conflicting", scenario_probability=0.20, ranking_score=0.90, conflicts_with_evidence=True
    )
    clean = make_scenario_outcome("clean", scenario_probability=0.70, ranking_score=0.20)

    chosen, _ = select_recommended_scenario([conflicting, clean])
    assert chosen == "clean"


def test_scenarios_that_raise_the_estimate_are_not_recommended() -> None:
    worse = make_scenario_outcome("worse", scenario_probability=0.95, ranking_score=0.80)

    chosen, reason = select_recommended_scenario([worse])
    assert chosen is None
    assert "No scenario lowered" in reason


def test_no_scenarios_at_all_is_reported_honestly() -> None:
    chosen, reason = select_recommended_scenario([])

    assert chosen is None
    assert "No scenario in the catalogue applies" in reason


def test_selection_is_deterministic_regardless_of_input_order() -> None:
    first = make_scenario_outcome("alpha", scenario_probability=0.50, ranking_score=0.40)
    second = make_scenario_outcome("beta", scenario_probability=0.50, ranking_score=0.40)

    assert select_recommended_scenario([first, second])[0] == "alpha"
    assert select_recommended_scenario([second, first])[0] == "alpha"
