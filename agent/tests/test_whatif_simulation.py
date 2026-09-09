"""End-to-end what-if tests against the real saved model and SHAP explainer.

Skipped automatically when the artifacts or the raw dataset are absent. Every
other what-if test uses synthetic fixtures and never touches the ML stack.
"""

from __future__ import annotations

import math

import pytest

from ml.src import config

VERIFICATION_CUSTOMER_ID = "7590-VHVEG"

REQUIRED_ARTIFACTS = [
    config.MODELS_DIR / config.BEST_MODEL_FILENAME,
    config.MODELS_DIR / config.PREPROCESSOR_FILENAME,
    config.MODELS_DIR / config.METADATA_FILENAME,
    config.RAW_DATA_DIR / config.RAW_DATASET_FILENAME,
]

pytestmark = pytest.mark.skipif(
    not all(path.exists() for path in REQUIRED_ARTIFACTS),
    reason="Trained model artifacts or raw dataset not available; run the ML pipeline first.",
)

# The Step 3 explanation for this customer, which the simulator must reproduce
# byte for byte. If these drift, something changed in the ML layer.
EXPECTED_BASELINE_PROBABILITY = 0.8064
EXPECTED_BASELINE_SHAP = {
    "tenure": 1.3752,
    "MonthlyCharges": 0.7998,
    "InternetService": -0.6895,
    "TotalCharges": -0.4549,
    "Contract": 0.4077,
}


@pytest.fixture(scope="module")
def customer_record() -> dict:
    from ml.src.prediction.predictor import load_customer_from_dataset

    return load_customer_from_dataset(row=None, customer_id=VERIFICATION_CUSTOMER_ID)


@pytest.fixture(scope="module")
def analysis(customer_record):
    from agent.simulation.comparison import compare_retention_scenarios

    return compare_retention_scenarios(customer_record)


# =========================================================
# 1. THE DOMAIN MATCHES THE REAL PREPROCESSOR
# =========================================================


def test_feature_domain_fixture_matches_the_fitted_preprocessor(feature_domain) -> None:
    """Keeps the fast unit-test fixture honest against the real artifacts."""
    from agent.simulation.feature_domain import domain_for

    real_domain = domain_for()

    assert real_domain.feature_order == feature_domain.feature_order
    assert real_domain.numeric_features == feature_domain.numeric_features
    assert real_domain.categorical_values == feature_domain.categorical_values


# =========================================================
# 2. BASELINE REPRODUCES THE EXISTING CONTRACTS
# =========================================================


def test_baseline_matches_the_existing_predictor(analysis, customer_record) -> None:
    from ml.src.prediction.predictor import predict_customer

    prediction = predict_customer(customer_record)

    assert analysis.baseline.churn_probability == prediction["churn_probability"]
    assert analysis.baseline.risk_level == prediction["risk_level"]
    assert analysis.baseline.prediction == prediction["prediction"]
    assert analysis.baseline.churn_probability == pytest.approx(EXPECTED_BASELINE_PROBABILITY)
    assert analysis.baseline.risk_level == "HIGH"


def test_baseline_shap_is_unchanged_from_step_three(analysis) -> None:
    actual = {driver.feature: driver.shap_value for driver in analysis.baseline.top_drivers}

    for feature, expected_shap in EXPECTED_BASELINE_SHAP.items():
        assert actual[feature] == pytest.approx(expected_shap, abs=1e-4)


# =========================================================
# 3. SCENARIOS USE THE SAME MODEL, NOT A NEW ONE
# =========================================================


def test_scenario_probability_comes_from_the_saved_model(analysis, customer_record) -> None:
    """Predicting the hypothetical profile directly must give the same number."""
    from ml.src.prediction.predictor import predict_customer

    outcome = next(o for o in analysis.scenarios if o.scenario_id == "two_year_contract")
    hypothetical = {**customer_record, "Contract": "Two year"}
    direct = predict_customer(hypothetical)

    assert outcome.scenario_probability == pytest.approx(direct["churn_probability"], abs=1e-4)
    assert outcome.scenario_risk_level == direct["risk_level"]


def test_no_retraining_occurs(analysis) -> None:
    """The artifacts on disk must be untouched by a simulation run."""
    from agent.simulation.comparison import compare_retention_scenarios
    from ml.src.prediction.predictor import load_customer_from_dataset

    before = {path: path.stat().st_mtime_ns for path in REQUIRED_ARTIFACTS}
    compare_retention_scenarios(
        load_customer_from_dataset(row=None, customer_id=VERIFICATION_CUSTOMER_ID)
    )
    after = {path: path.stat().st_mtime_ns for path in REQUIRED_ARTIFACTS}

    assert before == after


def test_model_version_is_consistent_across_scenarios(analysis, customer_record) -> None:
    from ml.src.explainability.explainer import explain_customer

    hypothetical = {**customer_record, "Contract": "One year"}
    scenario_explanation = explain_customer(hypothetical, top_k=1)

    assert scenario_explanation["model_version"] == analysis.baseline.model_version


# =========================================================
# 4. REAL SHAP ON BOTH SIDES
# =========================================================


def test_scenario_shap_is_real_and_additive(customer_record) -> None:
    """base_value + sum(SHAP) must equal the model's log-odds for the scenario too."""
    from ml.src.explainability.explainer import explain_customer
    from ml.src.prediction.predictor import get_predictor

    hypothetical = {**customer_record, "Contract": "Two year"}
    feature_count = len(get_predictor().feature_columns)
    explanation = explain_customer(hypothetical, top_k=feature_count)

    total = explanation["base_value"] + sum(
        driver["shap_value"] for driver in explanation["top_drivers"]
    )
    probability = explanation["churn_probability"]
    log_odds = math.log(probability / (1 - probability))

    assert total == pytest.approx(log_odds, abs=1e-3)


def test_shap_comparison_shows_what_moved(analysis) -> None:
    outcome = next(o for o in analysis.scenarios if o.scenario_id == "two_year_contract")
    deltas = {delta.feature: delta for delta in outcome.driver_deltas}

    # The changed feature moved...
    assert deltas["Contract"].changed_by_scenario is True
    assert deltas["Contract"].shap_change < 0
    assert deltas["Contract"].baseline_shap == pytest.approx(EXPECTED_BASELINE_SHAP["Contract"], abs=1e-4)

    # ...and untouched features did not, which is what makes the comparison readable.
    assert deltas["tenure"].shap_change == pytest.approx(0.0, abs=1e-9)
    assert deltas["tenure"].changed_by_scenario is False


def test_driver_deltas_are_sorted_by_movement(analysis) -> None:
    for outcome in analysis.scenarios:
        movements = [abs(delta.shap_change) for delta in outcome.driver_deltas]
        assert movements == sorted(movements, reverse=True)


# =========================================================
# 5. MULTI-SCENARIO COMPARISON
# =========================================================


def test_multiple_scenarios_are_evaluated_and_ranked(analysis) -> None:
    assert len(analysis.scenarios) >= 4
    scores = [outcome.ranking_score for outcome in analysis.scenarios]
    assert scores == sorted(scores, reverse=True)


def test_probability_change_arithmetic(analysis) -> None:
    for outcome in analysis.scenarios:
        expected = outcome.scenario_probability - outcome.baseline_probability
        assert outcome.absolute_probability_change == pytest.approx(expected, abs=1e-4)
        assert outcome.percentage_point_change == pytest.approx(expected * 100, abs=1e-2)


def test_risk_bands_use_the_existing_thresholds(analysis) -> None:
    """Risk levels come from the shared ML mapping; the simulator defines none of its own."""
    for outcome in analysis.scenarios:
        assert outcome.scenario_risk_level == config.risk_level_for(outcome.scenario_probability)
        assert outcome.baseline_risk_level == config.risk_level_for(outcome.baseline_probability)


def test_an_inapplicable_scenario_does_not_break_the_comparison(analysis) -> None:
    """This customer already has OnlineBackup, so the bundle scenario is skipped."""
    rejected_ids = {rejection.scenario_id for rejection in analysis.rejected_scenarios}

    assert "security_and_backup_bundle" in rejected_ids
    assert analysis.scenarios  # the rest still ran


def test_an_invalid_custom_scenario_is_reported_not_raised(customer_record) -> None:
    from agent.simulation.catalogue import build_custom_scenario, get_scenario
    from agent.simulation.comparison import compare_retention_scenarios

    broken = build_custom_scenario(
        scenario_id="broken_scenario",
        scenario_name="Broken Scenario",
        changed_features={"Contract": "18 months"},
        strategy_id="CONTRACT_CONVERSION",
        rationale="Deliberately invalid value.",
    )
    valid = get_scenario("two_year_contract")
    assert valid is not None

    result = compare_retention_scenarios(customer_record, scenarios=[broken, valid])

    assert [outcome.scenario_id for outcome in result.scenarios] == ["two_year_contract"]
    assert result.rejected_scenarios[0].scenario_id == "broken_scenario"
    assert "not a value the model learned" in result.rejected_scenarios[0].reason


# =========================================================
# 6. HONESTY AND GOVERNANCE
# =========================================================


def test_unsimulatable_interventions_are_surfaced(analysis) -> None:
    strategies = {item.strategy_id for item in analysis.unsimulatable_interventions}

    assert "EARLY_LIFECYCLE_ONBOARDING" in strategies
    for item in analysis.unsimulatable_interventions:
        assert item.simulatable is False


def test_every_result_carries_the_non_causal_disclaimer(analysis) -> None:
    from agent.models.scenario import WHATIF_DISCLAIMER

    assert WHATIF_DISCLAIMER in analysis.limitations
    for outcome in analysis.scenarios:
        assert WHATIF_DISCLAIMER in outcome.limitations


def test_generated_text_makes_no_causal_claim(analysis) -> None:
    from agent.guardrails import find_unsupported_claims

    texts = [analysis.selection_reason]
    texts.extend(outcome.model_based_interpretation for outcome in analysis.scenarios)

    assert find_unsupported_claims(*texts) == []


def test_human_approval_is_always_required(analysis) -> None:
    assert analysis.requires_human_approval is True


def test_full_analysis_with_deterministic_interpretation(customer_record) -> None:
    from agent.services.whatif_service import run_whatif_analysis
    from agent.simulation.report import render_whatif_report

    result = run_whatif_analysis(customer_record, provider=None)
    report = render_whatif_report(result)

    assert result.ai_interpretation
    assert result.requires_human_approval is True
    for heading in [
        "WHAT-IF RETENTION SIMULATION",
        "BASELINE",
        "SCENARIO COMPARISON",
        "AI INTERPRETATION",
        "HUMAN APPROVAL REQUIRED",
    ]:
        assert heading in report


def test_result_serialises_to_json(analysis) -> None:
    import json

    payload = json.loads(analysis.model_dump_json())

    assert payload["requires_human_approval"] is True
    assert payload["baseline"]["churn_probability"] == pytest.approx(EXPECTED_BASELINE_PROBABILITY)
