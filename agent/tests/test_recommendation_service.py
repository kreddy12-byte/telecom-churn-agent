"""Recommendation orchestration tests: fallback behaviour, safety, and schema."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from agent.guardrails import find_unsupported_claims
from agent.models.recommendation import (
    PROVIDER_DETERMINISTIC,
    RetentionRecommendation,
    SelectedStrategy,
)
from agent.providers.base import LLMResponseError, LLMTimeoutError, LLMUnavailableError
from agent.services.recommendation_service import RecommendationService
from agent.strategies.evaluator import evaluate_customer
from agent.tests.conftest import StubProvider, make_llm_payload


# =========================================================
# 1. DETERMINISTIC PATH (NO LLM CONFIGURED)
# =========================================================


def test_no_provider_uses_the_deterministic_engine(high_risk_evidence) -> None:
    result = RecommendationService(provider=None).recommend(high_risk_evidence)

    assert result.provider == PROVIDER_DETERMINISTIC
    assert result.fallback_reason is not None
    assert "No LLM provider is configured" in result.fallback_reason
    # The engine's top-ranked eligible play is used.
    assert result.selected_strategy.strategy_id == "EARLY_LIFECYCLE_ONBOARDING"


def test_deterministic_output_is_fully_populated(high_risk_evidence) -> None:
    result = RecommendationService(provider=None).recommend(high_risk_evidence)

    assert result.recommendation
    assert len(result.reasoning) >= 2
    assert result.supporting_evidence
    assert result.objective
    assert result.confidence in {"LOW", "MEDIUM", "HIGH"}
    assert result.limitations
    assert result.candidate_strategy_ids == evaluate_customer(high_risk_evidence).candidate_ids


def test_deterministic_path_is_labelled_honestly(high_risk_evidence) -> None:
    """The output must never imply an LLM wrote it when none did."""
    result = RecommendationService(provider=None).recommend(high_risk_evidence)

    assert result.generated_by_llm is False
    assert any("deterministic strategy engine" in item for item in result.limitations)


def test_deterministic_logic_invents_no_customer_facts(high_risk_evidence) -> None:
    """Generated prose may only mention features present in the evidence."""
    result = RecommendationService(provider=None).recommend(high_risk_evidence)
    text = " ".join([result.recommendation, *result.reasoning])

    known_features = {driver.feature for driver in high_risk_evidence.top_drivers}
    absent_features = {"StreamingTV", "OnlineSecurity", "PaymentMethod", "Dependents"}

    assert find_unsupported_claims(text) == []
    assert not absent_features & set(text.split())
    assert known_features & set(text.replace("(", " ").replace(")", " ").split())
    # Real values from the evidence, not invented ones.
    assert "0.87" in text


def test_escalation_when_no_strategy_matches(evidence_without_drivers) -> None:
    result = RecommendationService(provider=None).recommend(evidence_without_drivers)

    assert result.selected_strategy.strategy_id == "GENERAL_RETENTION_REVIEW"
    assert result.confidence == "LOW"
    assert result.requires_human_approval is True


# =========================================================
# 2. EVERY LLM FAILURE MODE FALLS BACK
# =========================================================


@pytest.mark.parametrize(
    ("provider", "expected_reason_fragment"),
    [
        (StubProvider(available=False), "not usable"),
        (StubProvider(error=LLMUnavailableError("missing key")), "LLMUnavailableError"),
        (StubProvider(error=LLMTimeoutError("timed out after 20s")), "LLMTimeoutError"),
        (StubProvider(error=LLMResponseError("empty message")), "LLMResponseError"),
        (StubProvider(response_text="not json at all"), "LLMResponseError"),
        (StubProvider(response_text=make_llm_payload(strategy_id="FREE_LAPTOP")), "not among the candidates"),
        (
            StubProvider(response_text=make_llm_payload(recommendation="Give them 50% off.")),
            "safety guardrail",
        ),
        (StubProvider(error=RuntimeError("provider bug")), "Unexpected LLM error"),
    ],
)
def test_llm_failures_degrade_to_the_deterministic_engine(
    provider: StubProvider, expected_reason_fragment: str, high_risk_evidence
) -> None:
    result = RecommendationService(provider=provider).recommend(high_risk_evidence)

    assert result.provider == PROVIDER_DETERMINISTIC
    assert result.fallback_reason is not None
    assert expected_reason_fragment in result.fallback_reason
    # A usable recommendation is still produced.
    assert result.recommendation
    assert result.requires_human_approval is True


def test_unavailable_provider_is_never_called(high_risk_evidence) -> None:
    provider = StubProvider(available=False)
    RecommendationService(provider=provider).recommend(high_risk_evidence)

    assert provider.calls == []


# =========================================================
# 3. AI PATH
# =========================================================


def test_valid_llm_output_is_used_and_attributed(high_risk_evidence) -> None:
    provider = StubProvider(response_text=make_llm_payload())
    result = RecommendationService(provider=provider).recommend(high_risk_evidence)

    assert result.provider == "stub:stub-model"
    assert result.fallback_reason is None
    assert result.generated_by_llm is True
    assert "onboarding" in result.recommendation.lower()
    assert len(provider.calls) == 1


def test_supporting_evidence_comes_from_shap_not_from_the_model(high_risk_evidence) -> None:
    """The LLM cannot alter a single number in the evidence block."""
    lying_payload = json.dumps(
        {
            "strategy_id": "EARLY_LIFECYCLE_ONBOARDING",
            "recommendation": "Schedule an onboarding call with this customer.",
            "reasoning": ["Short tenure is the strongest risk-increasing driver."],
            "supporting_evidence": [
                {"feature": "Invented", "value": "fake", "shap_value": 9.99, "direction": "increases_risk"}
            ],
            "churn_probability": 0.01,
        }
    )
    result = RecommendationService(provider=StubProvider(response_text=lying_payload)).recommend(
        high_risk_evidence
    )

    assert result.churn_probability == 0.87
    assert [item.feature for item in result.supporting_evidence] == ["tenure"]
    assert result.supporting_evidence[0].shap_value == pytest.approx(1.24)


def test_objective_always_comes_from_the_catalogue(high_risk_evidence) -> None:
    payload = json.dumps(
        {
            "strategy_id": "PRICING_VALUE",
            "recommendation": "Review the customer's charges against their plan.",
            "reasoning": ["Monthly charges influence the model's risk estimate."],
            "objective": "Make the customer happy at any cost.",
        }
    )
    result = RecommendationService(provider=StubProvider(response_text=payload)).recommend(
        high_risk_evidence
    )

    assert result.objective == "Improve perceived value for money without assuming a discount is required."


def test_llm_may_pick_a_lower_ranked_candidate(high_risk_evidence) -> None:
    """The AI ranks strategies; overriding the engine is allowed but costs confidence."""
    engine_choice = RecommendationService(provider=None).recommend(high_risk_evidence)
    payload = make_llm_payload(
        strategy_id="CONTRACT_CONVERSION",
        recommendation="Discuss longer-term contract options with this customer.",
        confidence=None,
    )
    ai_choice = RecommendationService(provider=StubProvider(response_text=payload)).recommend(
        high_risk_evidence
    )

    assert ai_choice.selected_strategy.strategy_id == "CONTRACT_CONVERSION"
    assert [item.feature for item in ai_choice.supporting_evidence] == ["Contract"]
    assert engine_choice.selected_strategy.strategy_id == "EARLY_LIFECYCLE_ONBOARDING"


# =========================================================
# 4. CONFIDENCE IS OWNED BY THE SYSTEM
# =========================================================


def test_llm_cannot_inflate_confidence(high_risk_evidence) -> None:
    computed = RecommendationService(provider=None).recommend(high_risk_evidence).confidence
    claimed_high = RecommendationService(
        provider=StubProvider(response_text=make_llm_payload(confidence="HIGH"))
    ).recommend(high_risk_evidence)

    assert computed == "MEDIUM"
    assert claimed_high.confidence == "MEDIUM"


def test_llm_can_lower_confidence(high_risk_evidence) -> None:
    result = RecommendationService(
        provider=StubProvider(response_text=make_llm_payload(confidence="LOW"))
    ).recommend(high_risk_evidence)

    assert result.confidence == "LOW"
    assert "Lowered from MEDIUM" in result.confidence_rationale


def test_model_caveats_are_kept_as_limitations(high_risk_evidence) -> None:
    payload = make_llm_payload(caveats=["The customer's support history was not supplied."])
    result = RecommendationService(provider=StubProvider(response_text=payload)).recommend(
        high_risk_evidence
    )

    assert "The customer's support history was not supplied." in result.limitations


# =========================================================
# 5. SCHEMA AND SAFETY INVARIANTS
# =========================================================


@pytest.mark.parametrize(
    "provider",
    [
        None,
        StubProvider(response_text=make_llm_payload()),
        StubProvider(error=LLMTimeoutError("slow")),
        StubProvider(response_text="garbage"),
    ],
)
def test_human_approval_is_always_required(provider, high_risk_evidence, low_risk_evidence) -> None:
    service = RecommendationService(provider=provider)
    for evidence in (high_risk_evidence, low_risk_evidence):
        assert service.recommend(evidence).requires_human_approval is True


def test_schema_forbids_auto_approval() -> None:
    """No code path — or compromised LLM reply — can disable human approval."""
    with pytest.raises(ValidationError, match="must always be True"):
        RetentionRecommendation(
            customer_id="X",
            churn_probability=0.5,
            risk_level="MEDIUM",
            selected_strategy=SelectedStrategy(strategy_id="A", strategy_name="A"),
            recommendation="Do something.",
            objective="Objective.",
            confidence="LOW",
            requires_human_approval=False,
        )


def test_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RetentionRecommendation(
            customer_id="X",
            churn_probability=0.5,
            risk_level="MEDIUM",
            selected_strategy=SelectedStrategy(strategy_id="A", strategy_name="A"),
            recommendation="Do something.",
            objective="Objective.",
            confidence="LOW",
            executed_action="email_sent",
        )


def test_recommendation_serialises_to_json(high_risk_evidence) -> None:
    result = RecommendationService(provider=None).recommend(high_risk_evidence)
    payload = json.loads(result.model_dump_json())

    assert payload["requires_human_approval"] is True
    assert payload["selected_strategy"]["strategy_id"] == "EARLY_LIFECYCLE_ONBOARDING"


def test_projection_onto_the_step_one_api_contract(high_risk_evidence) -> None:
    """Keeps the Step 1 shared contract usable when the endpoint is built."""
    result = RecommendationService(provider=None).recommend(high_risk_evidence)
    contract = result.to_api_contract()

    assert set(contract) == {
        "customer_id",
        "recommendation",
        "reason",
        "priority",
        "confidence",
        "requires_human_approval",
    }
    assert contract["priority"] == "HIGH"
    assert contract["requires_human_approval"] is True
