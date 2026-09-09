"""Scenario validation tests: feature domain, applicability, and impossible profiles."""

from __future__ import annotations

import math

import pytest

from agent.models.scenario import Scenario
from agent.simulation.catalogue import get_scenario
from agent.simulation.feature_domain import check_profile_consistency, check_value
from agent.simulation.validator import (
    ScenarioValidationError,
    apply_scenario,
    build_hypothetical_profile,
    check_applicability,
    validate_changed_features,
)


def make_scenario(changed_features: dict, **overrides) -> Scenario:
    payload = {
        "scenario_id": "test_scenario",
        "scenario_name": "Test Scenario",
        "description": "A scenario used in tests.",
        "changed_features": changed_features,
        "rationale": "Testing.",
        "strategy_id": "CONTRACT_CONVERSION",
    }
    payload.update(overrides)
    return Scenario(**payload)


# =========================================================
# 1. FEATURE-VALUE VALIDATION
# =========================================================


def test_valid_category_is_accepted(feature_domain) -> None:
    assert check_value("Contract", "One year", feature_domain) is None


def test_unknown_feature_is_rejected(feature_domain) -> None:
    reason = check_value("SupportQuality", "High", feature_domain)
    assert reason is not None and "not a feature of the trained model" in reason


def test_invalid_category_is_rejected(feature_domain) -> None:
    """'12 months' is not a smaller version of 'One year'; the encoder never saw it."""
    reason = check_value("Contract", "12 months", feature_domain)
    assert reason is not None and "not a value the model learned" in reason


def test_wrong_type_for_categorical_is_rejected(feature_domain) -> None:
    assert check_value("Contract", 12, feature_domain) is not None


def test_wrong_type_for_numeric_is_rejected(feature_domain) -> None:
    reason = check_value("MonthlyCharges", "cheap", feature_domain)
    assert reason is not None and "numeric" in reason


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_non_finite_numeric_is_rejected(value: float, feature_domain) -> None:
    assert check_value("MonthlyCharges", value, feature_domain) is not None


def test_negative_charges_are_rejected(feature_domain) -> None:
    reason = check_value("MonthlyCharges", -10.0, feature_domain)
    assert reason is not None and "negative" in reason


def test_binary_numeric_flag_is_enforced(feature_domain) -> None:
    assert check_value("SeniorCitizen", 1, feature_domain) is None
    assert check_value("SeniorCitizen", 7, feature_domain) is not None


def test_valid_numeric_change_is_accepted(feature_domain) -> None:
    assert check_value("MonthlyCharges", 24.85, feature_domain) is None
    assert math.isfinite(24.85)


def test_scenario_with_no_changes_is_rejected(feature_domain) -> None:
    with pytest.raises(ScenarioValidationError, match="nothing to evaluate"):
        validate_changed_features(make_scenario({}), feature_domain)


# =========================================================
# 2. APPLICABILITY TO A SPECIFIC CUSTOMER
# =========================================================


def test_applicable_scenario_passes(customer_profile) -> None:
    scenario = get_scenario("annual_contract")
    assert scenario is not None
    assert check_applicability(scenario, customer_profile) is None


def test_scenario_is_skipped_when_the_precondition_fails(customer_profile) -> None:
    profile = {**customer_profile, "Contract": "Two year"}
    scenario = get_scenario("annual_contract")
    assert scenario is not None

    reason = check_applicability(scenario, profile)
    assert reason is not None and "Two year" in reason


def test_no_op_scenario_is_rejected(customer_profile) -> None:
    """Simulating a change the customer already matches teaches nothing."""
    scenario = make_scenario({"Contract": "Month-to-month"})
    reason = check_applicability(scenario, customer_profile)

    assert reason is not None and "already matches" in reason


def test_missing_profile_field_blocks_applicability(customer_profile) -> None:
    profile = {key: value for key, value in customer_profile.items() if key != "Contract"}
    scenario = get_scenario("annual_contract")
    assert scenario is not None

    assert check_applicability(scenario, profile) is not None


# =========================================================
# 3. STRUCTURAL CONSISTENCY (IMPOSSIBLE COMBINATIONS)
# =========================================================


def test_real_profiles_are_consistent(customer_profile, no_internet_profile) -> None:
    assert check_profile_consistency(customer_profile) == []
    assert check_profile_consistency(no_internet_profile) == []


def test_addon_without_internet_is_impossible(no_internet_profile) -> None:
    contradictory = {**no_internet_profile, "TechSupport": "Yes"}
    violations = check_profile_consistency(contradictory)

    assert violations and "TechSupport" in violations[0]


def test_no_internet_service_value_requires_no_internet(customer_profile) -> None:
    """The reverse direction: the placeholder value is invalid when internet exists."""
    contradictory = {**customer_profile, "TechSupport": "No internet service"}
    violations = check_profile_consistency(contradictory)

    assert violations and "impossible" in violations[0]


def test_multiple_lines_requires_phone_service(customer_profile) -> None:
    contradictory = {**customer_profile, "MultipleLines": "Yes"}  # profile has PhoneService "No"
    violations = check_profile_consistency(contradictory)

    assert violations and "MultipleLines" in violations[0]


def test_impossible_scenario_is_rejected_end_to_end(no_internet_profile, feature_domain) -> None:
    scenario = get_scenario("tech_support_addon")
    assert scenario is not None

    with pytest.raises(ScenarioValidationError) as error:
        build_hypothetical_profile(scenario, no_internet_profile, feature_domain)

    # Caught as inapplicable first (TechSupport is "No internet service", not "No"),
    # which is the same protection arriving one step earlier.
    assert "tech_support_addon" in str(error.value)


def test_structurally_impossible_custom_scenario_is_rejected(
    no_internet_profile, feature_domain
) -> None:
    """A custom scenario with no applicability guard is still caught by consistency."""
    scenario = make_scenario({"TechSupport": "Yes"}, strategy_id="SUPPORT_INTERVENTION")

    with pytest.raises(ScenarioValidationError, match="impossible"):
        build_hypothetical_profile(scenario, no_internet_profile, feature_domain)


# =========================================================
# 4. BUILDING THE HYPOTHETICAL PROFILE
# =========================================================


def test_hypothetical_profile_applies_the_changes(customer_profile, feature_domain) -> None:
    scenario = get_scenario("annual_contract_with_support")
    assert scenario is not None

    hypothetical = build_hypothetical_profile(scenario, customer_profile, feature_domain)

    assert hypothetical["Contract"] == "One year"
    assert hypothetical["TechSupport"] == "Yes"
    # Everything else is carried over untouched.
    assert hypothetical["MonthlyCharges"] == customer_profile["MonthlyCharges"]


def test_original_customer_record_is_never_mutated(customer_profile) -> None:
    """A hypothetical must not write back onto real customer data."""
    original = dict(customer_profile)
    apply_scenario(customer_profile, make_scenario({"Contract": "Two year"}))

    assert customer_profile == original


def test_invalid_value_is_rejected_before_any_prediction(customer_profile, feature_domain) -> None:
    scenario = make_scenario({"Contract": "18 months"})

    with pytest.raises(ScenarioValidationError, match="not a value the model learned"):
        build_hypothetical_profile(scenario, customer_profile, feature_domain)
