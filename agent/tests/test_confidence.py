"""Confidence scoring tests."""

from __future__ import annotations

import pytest

from agent.confidence import assess_confidence, downgrade_only
from agent.strategies.evaluator import evaluate_customer


# =========================================================
# 1. CONSISTENCY
# =========================================================


def test_confidence_is_deterministic(high_risk_evidence) -> None:
    evaluation = evaluate_customer(high_risk_evidence)
    first = assess_confidence(high_risk_evidence, evaluation)
    second = assess_confidence(high_risk_evidence, evaluation)

    assert first.level == second.level
    assert first.score == pytest.approx(second.score)


def test_rationale_reports_every_factor(high_risk_evidence) -> None:
    evaluation = evaluate_customer(high_risk_evidence)
    assessment = assess_confidence(high_risk_evidence, evaluation)

    assert set(assessment.factors) == {
        "prediction_decisiveness",
        "evidence_alignment",
        "actionable_support",
        "discrimination",
    }
    assert "decisiveness" in assessment.rationale


def test_stronger_evidence_scores_higher(high_risk_evidence) -> None:
    """A driver that dominates the explanation should beat a marginal one."""
    weak_evidence = high_risk_evidence.model_copy(
        update={
            "top_drivers": [
                high_risk_evidence.top_drivers[0].model_copy(update={"impact": 0.05}),
                *high_risk_evidence.top_drivers[1:],
            ]
        }
    )

    strong = assess_confidence(high_risk_evidence, evaluate_customer(high_risk_evidence))
    weak = assess_confidence(weak_evidence, evaluate_customer(weak_evidence))

    assert strong.score > weak.score


def test_borderline_probability_reduces_confidence(high_risk_evidence) -> None:
    borderline = high_risk_evidence.model_copy(
        update={"churn_probability": 0.51, "risk_level": "MEDIUM"}
    )
    decisive = assess_confidence(high_risk_evidence, evaluate_customer(high_risk_evidence))
    uncertain = assess_confidence(borderline, evaluate_customer(borderline))

    assert uncertain.score < decisive.score


# =========================================================
# 2. HARD CAPS
# =========================================================


def test_escalation_fallback_is_never_above_low(evidence_without_drivers) -> None:
    evaluation = evaluate_customer(evidence_without_drivers)
    assessment = assess_confidence(evidence_without_drivers, evaluation)

    assert assessment.level == "LOW"
    assert "escalation fallback" in assessment.rationale


def test_low_risk_band_is_capped_at_medium(low_risk_evidence) -> None:
    evaluation = evaluate_customer(low_risk_evidence)
    assessment = assess_confidence(low_risk_evidence, evaluation)

    assert assessment.level in {"LOW", "MEDIUM"}


def test_overriding_the_top_ranked_strategy_removes_the_margin(high_risk_evidence) -> None:
    """Choosing a lower-ranked play is allowed, but it costs confidence."""
    evaluation = evaluate_customer(high_risk_evidence)
    runner_up = evaluation.candidates[1]

    top = assess_confidence(high_risk_evidence, evaluation)
    overridden = assess_confidence(high_risk_evidence, evaluation, selected=runner_up)

    assert overridden.factors["discrimination"] == 0.0
    assert overridden.score < top.score


# =========================================================
# 3. THE LLM MAY ONLY LOWER CONFIDENCE
# =========================================================


@pytest.mark.parametrize(
    ("computed", "claimed", "expected"),
    [
        ("MEDIUM", "HIGH", "MEDIUM"),  # inflation is ignored
        ("MEDIUM", "LOW", "LOW"),  # caution is respected
        ("HIGH", "MEDIUM", "MEDIUM"),
        ("LOW", "HIGH", "LOW"),
        ("MEDIUM", None, "MEDIUM"),
        ("MEDIUM", "VERY HIGH", "MEDIUM"),  # unparseable claims are ignored
    ],
)
def test_downgrade_only(computed, claimed, expected) -> None:
    assert downgrade_only(computed, claimed) == expected
