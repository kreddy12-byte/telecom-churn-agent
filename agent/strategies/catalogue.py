"""Controlled catalogue of retention strategies.

# =========================================================
# 1. DEFINE RETENTION STRATEGIES
# =========================================================

Why a catalogue instead of free-form LLM suggestions
----------------------------------------------------
A language model asked "how should we retain this customer?" will happily invent
offers the business does not sell, discounts nobody approved, and guarantees no
telco can make. This catalogue is the guard rail: the strategy engine scores
these plays against real SHAP evidence, and the LLM may only choose from the
candidates handed to it. Anything outside the catalogue is rejected.

Each entry is data, so a business stakeholder can review what the system is
allowed to propose without reading Python.
"""

from __future__ import annotations

from agent.models.strategy import RetentionStrategy

# --------------------------------------------------------------------- #
# A. CONTRACT_CONVERSION
# --------------------------------------------------------------------- #

CONTRACT_CONVERSION = RetentionStrategy(
    strategy_id="CONTRACT_CONVERSION",
    name="Contract Conversion",
    description=(
        "Engage the customer about moving from a rolling month-to-month agreement "
        "to a longer-term contract, subject to the incentives the business already offers."
    ),
    objective="Increase customer commitment and address contract-related churn risk.",
    applicable_risk_drivers=("Contract",),
    allowed_actions=(
        "Discuss longer-term contract options with the customer.",
        "Present an existing, approved contract incentive if the customer is eligible.",
        "Explain the benefits of contract stability relative to the current plan.",
    ),
    contraindications=(
        "Do not propose a conversion to a customer already on the longest contract.",
        "Do not promise pricing, incentives, or terms that have not been approved.",
    ),
    priority=1,
    excluded_profile_values={"Contract": ("Two year",)},
)

# --------------------------------------------------------------------- #
# B. PRICING_VALUE
# --------------------------------------------------------------------- #

PRICING_VALUE = RetentionStrategy(
    strategy_id="PRICING_VALUE",
    name="Pricing and Value Review",
    description=(
        "Review how the customer's charges compare with the value they receive, and "
        "position the plan accordingly. A discount is one possible outcome, not the default."
    ),
    objective="Improve perceived value for money without assuming a discount is required.",
    applicable_risk_drivers=("MonthlyCharges", "TotalCharges", "PaperlessBilling", "PaymentMethod"),
    allowed_actions=(
        "Review the customer's current charges against their usage and plan.",
        "Explain the value included in the current plan.",
        "Escalate to a retention specialist to consider an approved retention offer.",
        "Review billing and payment friction with the customer.",
    ),
    contraindications=(
        "Never quote a discount amount, percentage, or price that was not supplied by the business.",
        "Do not assume the customer considers the plan expensive; the model only indicates charges are influential.",
    ),
    priority=2,
)

# --------------------------------------------------------------------- #
# C. SUPPORT_INTERVENTION
# --------------------------------------------------------------------- #

SUPPORT_INTERVENTION = RetentionStrategy(
    strategy_id="SUPPORT_INTERVENTION",
    name="Support Intervention",
    description=(
        "Address service and support friction through proactive contact from a "
        "customer success or technical support specialist."
    ),
    objective="Resolve service friction and improve the customer's support experience.",
    applicable_risk_drivers=("TechSupport", "OnlineSecurity"),
    allowed_actions=(
        "Arrange a proactive service review call.",
        "Offer priority support handling for a defined period, where the business supports it.",
        "Walk the customer through support options included in their plan.",
    ),
    contraindications=(
        "Do not claim a specific fault or outage has occurred unless it is in the supplied data.",
        "Do not promise resolution timelines.",
    ),
    priority=3,
)

# --------------------------------------------------------------------- #
# D. SERVICE_BUNDLE_OPTIMIZATION
# --------------------------------------------------------------------- #

SERVICE_BUNDLE_OPTIMIZATION = RetentionStrategy(
    strategy_id="SERVICE_BUNDLE_OPTIMIZATION",
    name="Service Bundle Optimization",
    description=(
        "Review the customer's mix of services so the bundle matches what they actually use."
    ),
    objective="Improve service fit and the value the customer gets from their bundle.",
    applicable_risk_drivers=(
        "InternetService",
        "StreamingTV",
        "StreamingMovies",
        "OnlineBackup",
        "DeviceProtection",
        "MultipleLines",
        "PhoneService",
    ),
    allowed_actions=(
        "Review the current service bundle with the customer.",
        "Discuss adding or removing services to better match their usage.",
        "Explain services already included that the customer may not be using.",
    ),
    contraindications=(
        "Do not assume the customer is dissatisfied with a specific service.",
        "Do not quote prices for bundle changes that were not supplied.",
    ),
    priority=4,
)

# --------------------------------------------------------------------- #
# E. EARLY_LIFECYCLE_ONBOARDING
# --------------------------------------------------------------------- #

EARLY_LIFECYCLE_ONBOARDING = RetentionStrategy(
    strategy_id="EARLY_LIFECYCLE_ONBOARDING",
    name="Early Lifecycle Onboarding",
    description=(
        "Give a recently joined customer structured onboarding help so they reach "
        "the value of their service before the first renewal decision."
    ),
    objective="Improve early customer engagement during the highest-risk period of the lifecycle.",
    applicable_risk_drivers=("tenure",),
    allowed_actions=(
        "Schedule a personalised onboarding or welcome call.",
        "Provide service education tailored to the customer's plan.",
        "Run a proactive check-in on their first weeks of service.",
    ),
    contraindications=(
        "Not appropriate for long-tenured customers, for whom onboarding is irrelevant.",
        "Do not imply the customer has had problems unless the data shows it.",
    ),
    priority=2,
    # Onboarding only makes sense inside the first year of the relationship.
    max_tenure_months=12,
)

# --------------------------------------------------------------------- #
# F. GENERAL_RETENTION_REVIEW (fallback)
# --------------------------------------------------------------------- #

GENERAL_RETENTION_REVIEW = RetentionStrategy(
    strategy_id="GENERAL_RETENTION_REVIEW",
    name="General Retention Review",
    description=(
        "No specific play is clearly supported by the evidence, so a retention "
        "specialist should review the account and decide."
    ),
    objective="Escalate to a retention specialist for human review.",
    applicable_risk_drivers=(),
    allowed_actions=(
        "Route the account to a retention specialist for manual review.",
        "Summarise the model evidence for the specialist.",
    ),
    contraindications=(
        "Do not present this as a targeted offer; it is an escalation, not an intervention.",
    ),
    priority=9,
    is_fallback=True,
)


# =========================================================
# 2. CATALOGUE ACCESS
# =========================================================

STRATEGY_CATALOGUE: tuple[RetentionStrategy, ...] = (
    CONTRACT_CONVERSION,
    PRICING_VALUE,
    SUPPORT_INTERVENTION,
    SERVICE_BUNDLE_OPTIMIZATION,
    EARLY_LIFECYCLE_ONBOARDING,
    GENERAL_RETENTION_REVIEW,
)

FALLBACK_STRATEGY = GENERAL_RETENTION_REVIEW


def get_catalogue() -> tuple[RetentionStrategy, ...]:
    """Return every approved strategy."""
    return STRATEGY_CATALOGUE


def get_strategy(strategy_id: str) -> RetentionStrategy | None:
    """Look up a strategy by id; returns None for unknown ids.

    Used to reject any strategy an LLM invents.
    """
    for strategy in STRATEGY_CATALOGUE:
        if strategy.strategy_id == strategy_id:
            return strategy
    return None


def valid_strategy_ids() -> set[str]:
    """The complete set of ids the system will accept."""
    return {strategy.strategy_id for strategy in STRATEGY_CATALOGUE}
