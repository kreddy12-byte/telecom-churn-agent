"""Score the strategy catalogue against one customer's SHAP evidence.

The engine deliberately avoids rules like ``if churn > 0.7: offer_discount()``.
Such a rule ignores *why* the customer is at risk, which is exactly the
information the SHAP layer produces. Instead, each strategy declares which risk
drivers it addresses, and a strategy only becomes a candidate when the model's
own evidence shows those drivers pushing this customer toward churn.
"""

from __future__ import annotations

from agent.models.evidence import CustomerEvidence, DriverEvidence
from agent.models.strategy import RetentionStrategy, StrategyCandidate, StrategyEvaluation
from agent.strategies.catalogue import FALLBACK_STRATEGY, get_catalogue

# =========================================================
# 1. CHECK ELIGIBILITY
# =========================================================


def _tenure_in_months(evidence: CustomerEvidence) -> float | None:
    """Read tenure from the profile, or None when it is absent/unusable."""
    raw_value = evidence.profile_value("tenure")
    if raw_value is None:
        return None
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


def check_eligibility(strategy: RetentionStrategy, evidence: CustomerEvidence) -> str | None:
    """Return a rejection reason, or None when the strategy may be proposed.

    Eligibility is checked against the customer's *actual* profile values, so the
    system never suggests something contradictory such as converting a customer
    who already holds the longest available contract.
    """
    # Profile values that rule the strategy out entirely.
    for feature, blocked_values in strategy.excluded_profile_values.items():
        current_value = evidence.profile_value(feature)
        if current_value is None:
            continue
        if str(current_value).strip() in blocked_values:
            return f"{feature} is already '{current_value}'."

    # Lifecycle-stage guard.
    if strategy.max_tenure_months is not None:
        tenure = _tenure_in_months(evidence)
        if tenure is None:
            # Without tenure we cannot confirm the customer is early-lifecycle.
            # Refusing is safer than proposing onboarding to a 5-year customer.
            return "tenure was not supplied, so lifecycle eligibility cannot be confirmed."
        if tenure > strategy.max_tenure_months:
            return (
                f"tenure of {tenure:.0f} months exceeds the "
                f"{strategy.max_tenure_months}-month early-lifecycle window."
            )

    return None


# =========================================================
# 2. SCORE STRATEGIES AGAINST SHAP EVIDENCE
# =========================================================


def match_drivers(
    strategy: RetentionStrategy, evidence: CustomerEvidence
) -> tuple[DriverEvidence, ...]:
    """Risk-*increasing* drivers this strategy is designed to address.

    Protective drivers are excluded on purpose: a feature that is currently
    lowering the customer's risk is not a problem to intervene on.
    """
    applicable = set(strategy.applicable_risk_drivers)
    return tuple(
        driver for driver in evidence.risk_increasing_drivers if driver.feature in applicable
    )


def score_strategy(matched_drivers: tuple[DriverEvidence, ...]) -> float:
    """Sum the normalised SHAP impact of the drivers a strategy addresses.

    ``impact`` is already each driver's share of the customer's total absolute
    SHAP contribution, so the score reads directly as "this strategy targets X%
    of what moved the model's prediction".
    """
    return round(sum(driver.impact for driver in matched_drivers), 6)


def _describe_match(matched_drivers: tuple[DriverEvidence, ...]) -> str:
    """One-line, evidence-quoting explanation of why a strategy was shortlisted."""
    if not matched_drivers:
        return "No specific risk driver matched; retained as the escalation path."
    described = ", ".join(
        f"{driver.feature} (impact {driver.impact:.2f})" for driver in matched_drivers
    )
    return f"Addresses risk-increasing drivers: {described}."


# =========================================================
# 3. RANK CANDIDATES
# =========================================================


def evaluate_customer(evidence: CustomerEvidence) -> StrategyEvaluation:
    """Evaluate every catalogue strategy against this customer's evidence.

    Returns candidates sorted by evidence alignment (descending), with business
    priority used only to break ties. The fallback escalation strategy is always
    present, so the caller is never left without a valid option.
    """
    candidates: list[StrategyCandidate] = []
    rejected: list[tuple[str, str]] = []

    for strategy in get_catalogue():
        if strategy.is_fallback:
            continue  # handled separately in section 4

        rejection_reason = check_eligibility(strategy, evidence)
        if rejection_reason is not None:
            rejected.append((strategy.strategy_id, rejection_reason))
            continue

        matched_drivers = match_drivers(strategy, evidence)
        if not matched_drivers:
            rejected.append(
                (
                    strategy.strategy_id,
                    "no risk-increasing SHAP driver in this customer's evidence matches it.",
                )
            )
            continue

        candidates.append(
            StrategyCandidate(
                strategy=strategy,
                alignment_score=score_strategy(matched_drivers),
                matched_drivers=matched_drivers,
                rationale=_describe_match(matched_drivers),
            )
        )

    candidates.sort(
        key=lambda candidate: (
            -candidate.alignment_score,
            candidate.strategy.priority,
            candidate.strategy_id,
        )
    )

    # =========================================================
    # 4. GUARANTEE A FALLBACK
    # =========================================================

    # The escalation play is always available: when nothing else qualifies it is
    # the recommendation, and otherwise it remains a visible alternative for the
    # human reviewer.
    candidates.append(
        StrategyCandidate(
            strategy=FALLBACK_STRATEGY,
            alignment_score=0.0,
            matched_drivers=(),
            rationale=_describe_match(()),
        )
    )

    return StrategyEvaluation(candidates=tuple(candidates), rejected=tuple(rejected))
