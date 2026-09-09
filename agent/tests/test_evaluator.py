"""Evidence-based strategy evaluation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent.models.evidence import CustomerEvidence
from agent.strategies.catalogue import get_strategy
from agent.strategies.evaluator import check_eligibility, evaluate_customer


# =========================================================
# 1. NORMAL EVIDENCE
# =========================================================


def test_high_risk_customer_produces_expected_candidates(high_risk_evidence) -> None:
    evaluation = evaluate_customer(high_risk_evidence)

    assert "EARLY_LIFECYCLE_ONBOARDING" in evaluation.candidate_ids
    assert "PRICING_VALUE" in evaluation.candidate_ids
    assert "CONTRACT_CONVERSION" in evaluation.candidate_ids
    # The escalation path is always offered as a last resort.
    assert evaluation.candidate_ids[-1] == "GENERAL_RETENTION_REVIEW"


def test_candidates_are_ranked_by_evidence_alignment(high_risk_evidence) -> None:
    evaluation = evaluate_customer(high_risk_evidence)
    scores = [candidate.alignment_score for candidate in evaluation.candidates]

    assert scores == sorted(scores, reverse=True)
    # tenure carries the largest risk-increasing impact (0.35) for this customer.
    assert evaluation.best.strategy_id == "EARLY_LIFECYCLE_ONBOARDING"
    assert evaluation.best.alignment_score == pytest.approx(0.35)


def test_score_is_the_sum_of_matched_driver_impacts(high_risk_evidence) -> None:
    evaluation = evaluate_customer(high_risk_evidence)
    pricing = next(c for c in evaluation.candidates if c.strategy_id == "PRICING_VALUE")

    # MonthlyCharges (0.20) increases risk; TotalCharges (0.12) decreases it and
    # must not be counted as something to intervene on.
    assert pricing.alignment_score == pytest.approx(0.20)
    assert [driver.feature for driver in pricing.matched_drivers] == ["MonthlyCharges"]


def test_protective_drivers_do_not_create_candidates(high_risk_evidence) -> None:
    """InternetService lowers this customer's risk, so bundle optimisation is not proposed."""
    evaluation = evaluate_customer(high_risk_evidence)

    assert "SERVICE_BUNDLE_OPTIMIZATION" not in evaluation.candidate_ids
    rejected = dict(evaluation.rejected)
    assert "SERVICE_BUNDLE_OPTIMIZATION" in rejected


def test_rationale_quotes_the_matched_drivers(high_risk_evidence) -> None:
    evaluation = evaluate_customer(high_risk_evidence)
    assert "tenure" in evaluation.best.rationale


# =========================================================
# 2. ELIGIBILITY GUARDS
# =========================================================


def test_low_risk_customer_is_handled_without_contradictory_advice(low_risk_evidence) -> None:
    evaluation = evaluate_customer(low_risk_evidence)
    rejected = dict(evaluation.rejected)

    # Never propose converting a customer who already holds a two-year contract.
    assert "CONTRACT_CONVERSION" in rejected
    assert "Two year" in rejected["CONTRACT_CONVERSION"]
    # Onboarding is irrelevant after 60 months.
    assert "EARLY_LIFECYCLE_ONBOARDING" in rejected
    # The one genuine signal still surfaces.
    assert "SUPPORT_INTERVENTION" in evaluation.candidate_ids


def test_missing_tenure_blocks_the_lifecycle_strategy(high_risk_evidence) -> None:
    evidence = high_risk_evidence.model_copy(
        update={
            "customer_profile": {
                key: value
                for key, value in high_risk_evidence.customer_profile.items()
                if key != "tenure"
            }
        }
    )
    strategy = get_strategy("EARLY_LIFECYCLE_ONBOARDING")
    assert strategy is not None

    reason = check_eligibility(strategy, evidence)
    assert reason is not None and "tenure" in reason


def test_unparseable_tenure_is_treated_as_unknown(high_risk_evidence) -> None:
    evidence = high_risk_evidence.model_copy(
        update={"customer_profile": {**high_risk_evidence.customer_profile, "tenure": "n/a"}}
    )
    strategy = get_strategy("EARLY_LIFECYCLE_ONBOARDING")
    assert strategy is not None
    assert check_eligibility(strategy, evidence) is not None


# =========================================================
# 3. DEGENERATE EVIDENCE
# =========================================================


def test_missing_shap_drivers_fall_back_to_escalation(evidence_without_drivers) -> None:
    evaluation = evaluate_customer(evidence_without_drivers)

    assert evaluation.candidate_ids == ["GENERAL_RETENTION_REVIEW"]
    assert evaluation.best.strategy.is_fallback
    assert evaluation.best.alignment_score == 0.0


def test_only_protective_drivers_fall_back_to_escalation(low_risk_evidence) -> None:
    evidence = low_risk_evidence.model_copy(
        update={"top_drivers": [low_risk_evidence.top_drivers[0]]}  # Contract, decreases risk
    )
    evaluation = evaluate_customer(evidence)
    assert evaluation.best.strategy.is_fallback


# =========================================================
# 4. INVALID EVIDENCE IS REJECTED BEFORE IT REACHES THE ENGINE
# =========================================================


@pytest.mark.parametrize(
    "overrides",
    [
        {"churn_probability": 1.4},
        {"churn_probability": -0.1},
        {"risk_level": "CRITICAL"},
        {"prediction": 2},
        {"top_drivers": [{"feature": "tenure", "impact": 0.5, "direction": "maybe", "shap_value": 1.0}]},
        {"top_drivers": [{"feature": "tenure", "impact": 2.0, "direction": "increases_risk", "shap_value": 1.0}]},
    ],
)
def test_invalid_evidence_is_rejected(overrides: dict) -> None:
    payload = {
        "customer_id": "X",
        "churn_probability": 0.5,
        "risk_level": "MEDIUM",
        "prediction": 1,
        "top_drivers": [],
        **overrides,
    }
    with pytest.raises(ValidationError):
        CustomerEvidence(**payload)


def test_duplicate_drivers_are_rejected() -> None:
    """Duplicated features would double-count a driver during scoring."""
    driver = {
        "feature": "tenure",
        "value": 1,
        "impact": 0.3,
        "direction": "increases_risk",
        "shap_value": 1.0,
    }
    with pytest.raises(ValidationError):
        CustomerEvidence(
            churn_probability=0.5,
            risk_level="MEDIUM",
            prediction=1,
            top_drivers=[driver, driver],
        )


def test_unknown_evidence_fields_are_rejected() -> None:
    """Extra keys usually mean an upstream contract changed; fail loudly."""
    with pytest.raises(ValidationError):
        CustomerEvidence(
            churn_probability=0.5,
            risk_level="MEDIUM",
            prediction=1,
            top_drivers=[],
            competitor_offer="unlimited data",
        )


def test_from_explanation_requires_the_shap_contract() -> None:
    with pytest.raises(ValueError, match="missing required keys"):
        CustomerEvidence.from_explanation({"churn_probability": 0.5})
