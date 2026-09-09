"""Safety guardrail tests."""

from __future__ import annotations

import pytest

from agent.guardrails import (
    GuardrailViolation,
    assert_no_unsupported_claims,
    find_unsupported_claims,
)

SAFE_TEXT = (
    "Arrange a personalised onboarding call for this recently joined customer and review "
    "the services included in their current plan. A retention specialist should consider "
    "whether an approved retention offer is appropriate before any contact is made."
)


def test_compliant_text_passes() -> None:
    assert find_unsupported_claims(SAFE_TEXT) == []
    assert_no_unsupported_claims(SAFE_TEXT)  # must not raise


@pytest.mark.parametrize(
    ("text", "expected_rule"),
    [
        ("Offer the customer $20 off their monthly bill.", "fabricated_currency_amount"),
        ("Give them a 25% discount for six months.", "fabricated_percentage_offer"),
        ("Provide a free month of service.", "fabricated_free_offer"),
        ("We will waive the installation charge.", "fabricated_free_offer"),
        ("This offer guarantees the customer stays.", "outcome_guarantee"),
        ("A longer contract will prevent churn.", "outcome_guarantee"),
        ("The month-to-month contract causes churn for this customer.", "causal_claim"),
        ("A two-year contract will reduce churn for this customer.", "causal_effect_claim"),
        ("This scenario delivers a large churn reduction.", "causal_effect_claim"),
        ("Adding tech support lowers their churn.", "causal_effect_claim"),
        ("A longer contract prevents churn in cases like this.", "causal_effect_claim"),
        ("I have emailed the customer the new plan details.", "claimed_executed_action"),
        ("A discount has been applied to the account.", "claimed_executed_action"),
    ],
)
def test_unsupported_claims_are_detected(text: str, expected_rule: str) -> None:
    violations = find_unsupported_claims(text)
    assert violations, f"Expected {expected_rule} to be flagged in: {text}"
    assert any(violation.startswith(expected_rule) for violation in violations)


@pytest.mark.parametrize(
    "text",
    [
        "tenure accounts for 35% of this customer's total SHAP impact.",
        "Contract contributes 15 percent of the model's risk evidence.",
    ],
)
def test_percentages_describing_model_evidence_are_allowed(text: str) -> None:
    """Quoting SHAP impact is not the same as inventing a discount."""
    assert find_unsupported_claims(text) == []


def test_offer_percentage_is_still_caught_beside_evidence_percentages() -> None:
    """An allowed percentage in one bullet does not excuse an offer in another."""
    violations = find_unsupported_claims(
        "tenure accounts for 35% of the total SHAP impact.",
        "Give the customer 20% off their bill.",
    )

    assert len(violations) == 1
    assert "20%" in violations[0]


@pytest.mark.parametrize(
    "text",
    [
        "The trained model estimates a lower churn probability under this profile.",
        "This hypothetical profile reduces the model's churn probability estimate.",
        "The scenario lowers the churn risk estimate the model produces.",
        "Contract type contributes to the model's churn probability estimate.",
    ],
)
def test_model_estimate_phrasing_is_allowed(text: str) -> None:
    """The what-if layer must be able to describe its own results."""
    assert find_unsupported_claims(text) == []


def test_violations_across_multiple_fragments_are_collected() -> None:
    violations = find_unsupported_claims(SAFE_TEXT, "Offer 10% off.", "We guarantee retention.")
    rule_names = {violation.split(":", 1)[0] for violation in violations}

    assert rule_names == {"fabricated_percentage_offer", "outcome_guarantee"}


def test_duplicate_violations_are_reported_once() -> None:
    violations = find_unsupported_claims("Offer 10% off.", "Offer 10% off again.")
    assert len(violations) == 1


def test_assert_raises_on_violation() -> None:
    with pytest.raises(GuardrailViolation, match="fabricated_currency_amount"):
        assert_no_unsupported_claims("Credit the account with $50.")
