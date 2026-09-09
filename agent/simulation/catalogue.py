"""Controlled catalogue of what-if scenarios.

# =========================================================
# 1. DEFINE HYPOTHETICAL PROFILES
# =========================================================

Each scenario names a small, defensible change to a customer's profile using
features the trained model actually consumes, and ties it to a retention
strategy from the Step 4 catalogue. Neither the caller nor the LLM may invent a
scenario: arbitrary profiles are exactly how a simulator starts producing
authoritative-looking nonsense.

# =========================================================
# 2. WHAT IS DELIBERATELY *NOT* HERE
# =========================================================

Two categories are excluded on principle:

* **Interventions with no feature.** A proactive support call or onboarding help
  has no representation in the model. Those live in
  ``UNSIMULATABLE_INTERVENTIONS`` and are reported honestly rather than
  approximated.
* **Discount scenarios with invented amounts.** ``MonthlyCharges`` is a model
  feature, so a price change *is* technically simulatable — but only if the
  business supplies the amount. Guessing one would fabricate an offer, which the
  Step 4 guardrails exist to prevent. Callers with a real approved figure can
  build a custom scenario (see :func:`build_custom_scenario`).

# =========================================================
# 3. A SHARED CAVEAT ABOUT ADD-ONS
# =========================================================

Turning a service add-on on in a hypothetical profile holds ``MonthlyCharges``
constant. If the add-on carries a fee, the realistic profile would also show
higher charges, which the model treats as a separate risk driver. Every add-on
scenario carries this caveat rather than hiding it.
"""

from __future__ import annotations

from typing import Any

from agent.models.scenario import Scenario, UnsimulatableIntervention

ADD_ON_PRICING_CAVEAT = (
    "The hypothetical profile holds MonthlyCharges constant. If this add-on carries a "
    "fee, a realistic profile would also show higher charges, which the model treats as "
    "a separate risk driver."
)

CONTRACT_COMMITMENT_CAVEAT = (
    "The profile change assumes the customer would accept a longer commitment; the model "
    "has no feature representing willingness to commit."
)


# =========================================================
# 4. SCENARIO DEFINITIONS
# =========================================================

ANNUAL_CONTRACT = Scenario(
    scenario_id="annual_contract",
    scenario_name="Move to One-Year Contract",
    description="Hypothetically change the customer's contract type to a one-year term.",
    changed_features={"Contract": "One year"},
    rationale=(
        "Contract type is one of the strongest features in the trained model. This "
        "evaluates how the model responds to a one-year commitment profile."
    ),
    strategy_id="CONTRACT_CONVERSION",
    limitations=(CONTRACT_COMMITMENT_CAVEAT,),
    applicable_when={"Contract": ("Month-to-month",)},
)

TWO_YEAR_CONTRACT = Scenario(
    scenario_id="two_year_contract",
    scenario_name="Move to Two-Year Contract",
    description="Hypothetically change the customer's contract type to a two-year term.",
    changed_features={"Contract": "Two year"},
    rationale=(
        "A stronger commitment profile than the one-year scenario; comparing the two "
        "shows how the model's estimate responds to commitment length."
    ),
    strategy_id="CONTRACT_CONVERSION",
    limitations=(CONTRACT_COMMITMENT_CAVEAT,),
    applicable_when={"Contract": ("Month-to-month", "One year")},
)

TECH_SUPPORT_ADDON = Scenario(
    scenario_id="tech_support_addon",
    scenario_name="Add Technical Support Service",
    description="Hypothetically enable the technical support add-on on the customer's account.",
    changed_features={"TechSupport": "Yes"},
    rationale=(
        "TechSupport is a real service-configuration feature in the model. It represents "
        "whether the customer subscribes to the support add-on — not the quality of "
        "support they receive."
    ),
    strategy_id="SUPPORT_INTERVENTION",
    limitations=(
        ADD_ON_PRICING_CAVEAT,
        "TechSupport records subscription to a support product, so this scenario cannot "
        "represent improved service quality or a human intervention.",
    ),
    # "No" only occurs for customers who have internet, so this also guarantees
    # the resulting profile is structurally valid.
    applicable_when={"TechSupport": ("No",)},
)

ONLINE_SECURITY_ADDON = Scenario(
    scenario_id="online_security_addon",
    scenario_name="Add Online Security Service",
    description="Hypothetically enable the online security add-on on the customer's account.",
    changed_features={"OnlineSecurity": "Yes"},
    rationale=(
        "OnlineSecurity is among the service features the model uses, and appears in the "
        "support-related risk drivers of the Step 4 strategy catalogue."
    ),
    strategy_id="SUPPORT_INTERVENTION",
    limitations=(ADD_ON_PRICING_CAVEAT,),
    applicable_when={"OnlineSecurity": ("No",)},
)

SECURITY_AND_BACKUP_BUNDLE = Scenario(
    scenario_id="security_and_backup_bundle",
    scenario_name="Add Security and Backup Bundle",
    description=(
        "Hypothetically enable both the online security and online backup add-ons, "
        "representing a fuller service bundle."
    ),
    changed_features={"OnlineSecurity": "Yes", "OnlineBackup": "Yes"},
    rationale=(
        "Evaluates whether the model responds differently to a broader service "
        "configuration than to a single add-on."
    ),
    strategy_id="SERVICE_BUNDLE_OPTIMIZATION",
    limitations=(ADD_ON_PRICING_CAVEAT,),
    applicable_when={"OnlineSecurity": ("No",), "OnlineBackup": ("No",)},
)

AUTOMATIC_PAYMENT_METHOD = Scenario(
    scenario_id="automatic_payment_method",
    scenario_name="Switch to Automatic Bank Payment",
    description=(
        "Hypothetically change the payment method to automatic bank transfer, removing "
        "manual payment friction."
    ),
    changed_features={"PaymentMethod": "Bank transfer (automatic)"},
    rationale=(
        "PaymentMethod is a model feature and a billing-experience change the business "
        "can offer without inventing any pricing or discount."
    ),
    strategy_id="PRICING_VALUE",
    limitations=(
        "Payment method reflects a billing arrangement, not the amount the customer pays.",
    ),
    applicable_when={"PaymentMethod": ("Electronic check", "Mailed check")},
)

# --- Multi-factor scenario ---------------------------------------------- #

ANNUAL_CONTRACT_WITH_SUPPORT = Scenario(
    scenario_id="annual_contract_with_support",
    scenario_name="One-Year Contract with Technical Support",
    description=(
        "Hypothetically combine a one-year contract with the technical support add-on."
    ),
    changed_features={"Contract": "One year", "TechSupport": "Yes"},
    rationale=(
        "Combines the two individually simulatable changes so the model's response to a "
        "package can be compared against each change on its own."
    ),
    strategy_id="CONTRACT_CONVERSION",
    limitations=(
        CONTRACT_COMMITMENT_CAVEAT,
        ADD_ON_PRICING_CAVEAT,
        "Combined scenarios compound their individual assumptions, so treat the estimate "
        "with more caution than a single-feature scenario.",
    ),
    applicable_when={"Contract": ("Month-to-month",), "TechSupport": ("No",)},
)


SCENARIO_CATALOGUE: tuple[Scenario, ...] = (
    ANNUAL_CONTRACT,
    TWO_YEAR_CONTRACT,
    TECH_SUPPORT_ADDON,
    ONLINE_SECURITY_ADDON,
    SECURITY_AND_BACKUP_BUNDLE,
    AUTOMATIC_PAYMENT_METHOD,
    ANNUAL_CONTRACT_WITH_SUPPORT,
)


# =========================================================
# 5. INTERVENTIONS THE MODEL CANNOT REPRESENT
# =========================================================

UNSIMULATABLE_INTERVENTIONS: tuple[UnsimulatableIntervention, ...] = (
    UnsimulatableIntervention(
        strategy_id="SUPPORT_INTERVENTION",
        intervention="Proactive service review call or priority support handling",
        reason=(
            "The trained model contains no feature representing support quality, response "
            "time, or human outreach. Only subscription to the TechSupport and "
            "OnlineSecurity products is modelled."
        ),
    ),
    UnsimulatableIntervention(
        strategy_id="EARLY_LIFECYCLE_ONBOARDING",
        intervention="Personalised onboarding, service education, or a proactive check-in",
        reason=(
            "The model has no feature representing onboarding activity. The related "
            "feature, tenure, records how long the customer has been with the operator "
            "and is a historical fact that no intervention can change."
        ),
    ),
    UnsimulatableIntervention(
        strategy_id="PRICING_VALUE",
        intervention="Targeted discount or retention offer",
        reason=(
            "MonthlyCharges is a model feature, so a price change is technically "
            "simulatable — but only with an offer amount supplied by the business. "
            "Inventing an amount would fabricate an offer, so no catalogue scenario does."
        ),
    ),
    UnsimulatableIntervention(
        strategy_id="GENERAL_RETENTION_REVIEW",
        intervention="Escalation to a retention specialist",
        reason=(
            "Escalation is an internal process that changes nothing about the customer's "
            "profile, so there is no hypothetical profile to evaluate."
        ),
    ),
)


# =========================================================
# 6. CATALOGUE ACCESS
# =========================================================


def get_scenario_catalogue() -> tuple[Scenario, ...]:
    """Every approved what-if scenario."""
    return SCENARIO_CATALOGUE


def get_scenario(scenario_id: str) -> Scenario | None:
    """Look up a scenario by id; returns None for unknown ids."""
    for scenario in SCENARIO_CATALOGUE:
        if scenario.scenario_id == scenario_id:
            return scenario
    return None


def valid_scenario_ids() -> set[str]:
    return {scenario.scenario_id for scenario in SCENARIO_CATALOGUE}


def scenarios_for_strategy(strategy_id: str) -> tuple[Scenario, ...]:
    """Scenarios that represent a given retention strategy."""
    return tuple(
        scenario for scenario in SCENARIO_CATALOGUE if scenario.strategy_id == strategy_id
    )


def unsimulatable_for_strategies(strategy_ids: set[str]) -> tuple[UnsimulatableIntervention, ...]:
    """Unsimulatable interventions relevant to a customer's candidate strategies."""
    return tuple(
        intervention
        for intervention in UNSIMULATABLE_INTERVENTIONS
        if intervention.strategy_id in strategy_ids
    )


def build_custom_scenario(
    scenario_id: str,
    scenario_name: str,
    changed_features: dict[str, Any],
    strategy_id: str,
    rationale: str,
    description: str = "",
    limitations: tuple[str, ...] = (),
) -> Scenario:
    """Construct a one-off scenario from caller-supplied values.

    This is the supported path for changes the catalogue deliberately omits —
    most importantly a price change with a real, business-approved amount. The
    resulting scenario goes through exactly the same validation as a catalogue
    entry, so an invalid feature or value is still rejected.
    """
    return Scenario(
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        description=description or f"Custom hypothetical profile: {changed_features}.",
        changed_features=dict(changed_features),
        rationale=rationale,
        strategy_id=strategy_id,
        limitations=limitations
        + ("This scenario was supplied by the caller rather than the approved catalogue.",),
    )
