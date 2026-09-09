"""Scenario validation.

# =========================================================
# 1. VALIDATE SCENARIO
# =========================================================

Three questions, in order:

1. **Are the changed features real and their values learnable?** Checked against
   the fitted preprocessor's domain (``feature_domain.py``).
2. **Does the scenario apply to this customer?** There is nothing to learn from
   simulating a move to a one-year contract for a customer already on one.
3. **Is the resulting profile physically possible?** The dataset has structural
   dependencies (no internet implies no internet add-ons), and a hypothetical
   profile that violates them describes a customer who cannot exist.

Only when all three pass does anything reach the model.
"""

from __future__ import annotations

from typing import Any, Mapping

from agent.models.scenario import Scenario
from agent.simulation.feature_domain import (
    FeatureDomain,
    check_profile_consistency,
    check_value,
)


class ScenarioValidationError(ValueError):
    """Raised when a scenario cannot be evaluated for a customer.

    Carries the scenario id so a multi-scenario comparison can report which one
    failed and keep going.
    """

    def __init__(self, scenario_id: str, reason: str) -> None:
        self.scenario_id = scenario_id
        self.reason = reason
        super().__init__(f"Scenario '{scenario_id}' cannot be evaluated: {reason}")


# =========================================================
# 2. FEATURE-LEVEL CHECKS
# =========================================================


def validate_changed_features(scenario: Scenario, domain: FeatureDomain) -> None:
    """Every changed feature must exist and carry a value the model learned."""
    if not scenario.changed_features:
        raise ScenarioValidationError(
            scenario.scenario_id, "it changes no features, so there is nothing to evaluate."
        )

    for feature, value in scenario.changed_features.items():
        rejection = check_value(feature, value, domain)
        if rejection is not None:
            raise ScenarioValidationError(scenario.scenario_id, rejection)


# =========================================================
# 3. CUSTOMER-LEVEL APPLICABILITY
# =========================================================


def check_applicability(scenario: Scenario, profile: Mapping[str, Any]) -> str | None:
    """Return why the scenario does not apply to this customer, or None.

    Two ways a scenario can fail to apply: the customer's current values are
    outside the scenario's precondition, or the change would be a no-op.
    """
    for feature, allowed_current_values in scenario.applicable_when.items():
        if feature not in profile:
            return f"the customer profile does not include '{feature}'."
        current = str(profile[feature]).strip()
        if current not in allowed_current_values:
            return (
                f"{feature} is currently '{current}', and this scenario applies only to "
                f"{list(allowed_current_values)}."
            )

    unchanged = [
        feature
        for feature, new_value in scenario.changed_features.items()
        if feature in profile and str(profile[feature]).strip() == str(new_value)
    ]
    if len(unchanged) == len(scenario.changed_features):
        return "the customer already matches this profile, so the scenario changes nothing."

    return None


# =========================================================
# 4. BUILD AND CHECK THE HYPOTHETICAL PROFILE
# =========================================================


def apply_scenario(profile: Mapping[str, Any], scenario: Scenario) -> dict[str, Any]:
    """Return a copy of the profile with the scenario's changes applied.

    A copy, never an in-place edit: the caller's customer record is real data and
    must not be mutated by a hypothetical.
    """
    hypothetical = dict(profile)
    hypothetical.update(scenario.changed_features)
    return hypothetical


def build_hypothetical_profile(
    scenario: Scenario, profile: Mapping[str, Any], domain: FeatureDomain
) -> dict[str, Any]:
    """Validate a scenario for one customer and return the hypothetical profile.

    Raises:
        ScenarioValidationError: invalid feature, invalid value, inapplicable
            scenario, or a structurally impossible resulting profile.
    """
    validate_changed_features(scenario, domain)

    inapplicable_reason = check_applicability(scenario, profile)
    if inapplicable_reason is not None:
        raise ScenarioValidationError(scenario.scenario_id, inapplicable_reason)

    hypothetical = apply_scenario(profile, scenario)

    # Consistency is checked on the result, not the change, because a change is
    # only contradictory in combination with the rest of the profile.
    violations = check_profile_consistency(hypothetical)
    if violations:
        raise ScenarioValidationError(
            scenario.scenario_id,
            "the resulting profile is impossible: " + " ".join(violations),
        )

    return hypothetical
