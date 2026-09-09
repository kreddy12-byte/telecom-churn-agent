"""What-if scenario catalogue integrity tests."""

from __future__ import annotations

import pytest

from agent.simulation.catalogue import (
    SCENARIO_CATALOGUE,
    UNSIMULATABLE_INTERVENTIONS,
    build_custom_scenario,
    get_scenario,
    scenarios_for_strategy,
    valid_scenario_ids,
)
from agent.simulation.feature_domain import check_value
from agent.strategies.catalogue import valid_strategy_ids


# =========================================================
# 1. CATALOGUE INTEGRITY
# =========================================================


def test_catalogue_loads() -> None:
    assert SCENARIO_CATALOGUE
    assert len(valid_scenario_ids()) == len(SCENARIO_CATALOGUE)


def test_every_scenario_has_required_fields() -> None:
    for scenario in SCENARIO_CATALOGUE:
        assert scenario.scenario_id and scenario.scenario_id.islower()
        assert scenario.scenario_name
        assert scenario.description
        assert scenario.rationale
        assert scenario.changed_features
        assert scenario.strategy_id


def test_scenarios_reference_real_retention_strategies() -> None:
    """A scenario must map to a strategy the Step 4 catalogue actually defines."""
    for scenario in SCENARIO_CATALOGUE:
        assert scenario.strategy_id in valid_strategy_ids(), scenario.scenario_id


def test_scenarios_only_change_real_model_features(feature_domain) -> None:
    """Guards against a catalogue entry drifting away from the model schema."""
    for scenario in SCENARIO_CATALOGUE:
        for feature, value in scenario.changed_features.items():
            assert check_value(feature, value, feature_domain) is None, (
                f"{scenario.scenario_id} sets an invalid {feature}={value!r}"
            )


def test_scenarios_are_immutable() -> None:
    scenario = get_scenario("annual_contract")
    assert scenario is not None
    with pytest.raises(Exception):
        scenario.scenario_name = "Something else"  # type: ignore[misc]


def test_lookup_rejects_unknown_scenario() -> None:
    assert get_scenario("annual_contract") is not None
    assert get_scenario("free_upgrade_forever") is None


def test_scenarios_for_strategy() -> None:
    contract_scenarios = scenarios_for_strategy("CONTRACT_CONVERSION")

    assert {scenario.scenario_id for scenario in contract_scenarios} >= {
        "annual_contract",
        "two_year_contract",
    }
    assert scenarios_for_strategy("GENERAL_RETENTION_REVIEW") == ()


def test_multi_factor_scenario_changes_several_features() -> None:
    scenario = get_scenario("annual_contract_with_support")
    assert scenario is not None
    assert set(scenario.changed_features) == {"Contract", "TechSupport"}


def test_addon_scenarios_disclose_the_pricing_assumption() -> None:
    """Holding MonthlyCharges constant while adding a paid service is an assumption."""
    for scenario_id in ("tech_support_addon", "online_security_addon"):
        scenario = get_scenario(scenario_id)
        assert scenario is not None
        assert any("MonthlyCharges constant" in item for item in scenario.limitations)


# =========================================================
# 2. UNSIMULATABLE INTERVENTIONS
# =========================================================


def test_unsimulatable_interventions_are_declared() -> None:
    assert UNSIMULATABLE_INTERVENTIONS
    for intervention in UNSIMULATABLE_INTERVENTIONS:
        assert intervention.simulatable is False
        assert intervention.strategy_id in valid_strategy_ids()
        assert intervention.intervention
        assert intervention.reason


def test_human_only_interventions_are_marked_unsimulatable() -> None:
    """Onboarding and support calls have no representation in the model."""
    covered = {item.strategy_id for item in UNSIMULATABLE_INTERVENTIONS}

    assert "EARLY_LIFECYCLE_ONBOARDING" in covered
    assert "SUPPORT_INTERVENTION" in covered
    assert "GENERAL_RETENTION_REVIEW" in covered


def test_no_catalogue_scenario_invents_a_discount() -> None:
    """Pricing changes need a business-supplied amount, so none is hardcoded."""
    for scenario in SCENARIO_CATALOGUE:
        assert "MonthlyCharges" not in scenario.changed_features
        assert "TotalCharges" not in scenario.changed_features

    pricing = [
        item for item in UNSIMULATABLE_INTERVENTIONS if item.strategy_id == "PRICING_VALUE"
    ]
    assert pricing and "amount supplied by the business" in pricing[0].reason


def test_no_scenario_changes_a_historical_fact() -> None:
    """tenure records history; no intervention can change how long someone has been a customer."""
    for scenario in SCENARIO_CATALOGUE:
        assert "tenure" not in scenario.changed_features


# =========================================================
# 3. CUSTOM SCENARIOS
# =========================================================


def test_custom_scenario_is_flagged_as_caller_supplied() -> None:
    scenario = build_custom_scenario(
        scenario_id="approved_price_change",
        scenario_name="Approved Price Change",
        changed_features={"MonthlyCharges": 24.85},
        strategy_id="PRICING_VALUE",
        rationale="The business supplied an approved retention price for this customer.",
    )

    assert scenario.changed_features == {"MonthlyCharges": 24.85}
    assert any("supplied by the caller" in item for item in scenario.limitations)
