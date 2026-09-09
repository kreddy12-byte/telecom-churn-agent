"""AI reasoning layer tests — all with mocked provider responses."""

from __future__ import annotations

import json

import pytest

from agent.guardrails import GuardrailViolation
from agent.prompts.retention_prompt import RETENTION_SYSTEM_PROMPT, build_reasoning_prompt
from agent.providers.base import LLMResponseError
from agent.services.reasoning_service import ReasoningService
from agent.strategies.evaluator import evaluate_customer
from agent.tests.conftest import StubProvider, make_llm_payload


def reason_with(response_text: str, evidence):
    """Run the reasoning service against a canned LLM reply."""
    evaluation = evaluate_customer(evidence)
    service = ReasoningService(StubProvider(response_text=response_text))
    return service.generate(evidence, evaluation)


# =========================================================
# 1. PROMPT CONSTRUCTION
# =========================================================


def test_prompt_contains_the_evidence_and_only_approved_strategies(high_risk_evidence) -> None:
    evaluation = evaluate_customer(high_risk_evidence)
    prompt = json.loads(build_reasoning_prompt(high_risk_evidence, evaluation))

    assert prompt["model_prediction"]["churn_probability"] == 0.87
    assert [d["feature"] for d in prompt["shap_explanation"]["drivers"]][0] == "tenure"
    assert [s["strategy_id"] for s in prompt["candidate_strategies"]] == evaluation.candidate_ids
    # Constraints travel with the strategies so the model can respect them.
    assert prompt["candidate_strategies"][0]["contraindications"]


def test_system_prompt_states_the_non_negotiable_rules() -> None:
    for rule in ["Never invent", "human approval", "SHAP", "JSON"]:
        assert rule in RETENTION_SYSTEM_PROMPT


# =========================================================
# 2. HAPPY PATH
# =========================================================


def test_valid_response_is_accepted(high_risk_evidence) -> None:
    reasoning = reason_with(make_llm_payload(), high_risk_evidence)

    assert reasoning.strategy_id == "EARLY_LIFECYCLE_ONBOARDING"
    assert reasoning.recommendation
    assert len(reasoning.reasoning) == 2
    assert reasoning.claimed_confidence == "HIGH"
    assert reasoning.provider_label == "stub:stub-model"


def test_code_fences_are_tolerated(high_risk_evidence) -> None:
    """Models often wrap JSON in markdown despite instructions not to."""
    fenced = f"```json\n{make_llm_payload()}\n```"
    assert reason_with(fenced, high_risk_evidence).strategy_id == "EARLY_LIFECYCLE_ONBOARDING"


def test_single_string_reasoning_is_normalised(high_risk_evidence) -> None:
    payload = json.dumps(
        {
            "strategy_id": "PRICING_VALUE",
            "recommendation": "Review the customer's current charges with them.",
            "reasoning": "Monthly charges are an influential risk driver.",
        }
    )
    assert reason_with(payload, high_risk_evidence).reasoning == [
        "Monthly charges are an influential risk driver."
    ]


def test_unusable_confidence_claim_is_dropped(high_risk_evidence) -> None:
    payload = make_llm_payload(confidence="extremely sure")
    assert reason_with(payload, high_risk_evidence).claimed_confidence is None


# =========================================================
# 3. INVALID OUTPUT IS REJECTED
# =========================================================


@pytest.mark.parametrize(
    "response_text",
    [
        "I think you should call the customer.",  # not JSON at all
        "{'strategy_id': 'PRICING_VALUE'}",  # single quotes
        "[1, 2, 3]",  # JSON, but not an object
        "",
    ],
)
def test_invalid_json_is_rejected(response_text: str, high_risk_evidence) -> None:
    with pytest.raises(LLMResponseError):
        reason_with(response_text, high_risk_evidence)


def test_strategy_outside_the_catalogue_is_rejected(high_risk_evidence) -> None:
    payload = make_llm_payload(strategy_id="FREE_IPHONE_GIVEAWAY")
    with pytest.raises(LLMResponseError, match="not among the candidates"):
        reason_with(payload, high_risk_evidence)


def test_ineligible_catalogue_strategy_is_rejected(low_risk_evidence) -> None:
    """A real strategy that was ruled out for this customer is still invalid."""
    payload = make_llm_payload(strategy_id="CONTRACT_CONVERSION")
    with pytest.raises(LLMResponseError, match="not among the candidates"):
        reason_with(payload, low_risk_evidence)


@pytest.mark.parametrize(
    "payload",
    [
        {"recommendation": "Call them.", "reasoning": ["a"]},  # no strategy_id
        {"strategy_id": "PRICING_VALUE", "reasoning": ["a"]},  # no recommendation
        {"strategy_id": "PRICING_VALUE", "recommendation": "  ", "reasoning": ["a"]},
        {"strategy_id": "PRICING_VALUE", "recommendation": "Call them.", "reasoning": []},
    ],
)
def test_incomplete_response_is_rejected(payload: dict, high_risk_evidence) -> None:
    with pytest.raises(LLMResponseError):
        reason_with(json.dumps(payload), high_risk_evidence)


def test_overlong_recommendation_is_rejected(high_risk_evidence) -> None:
    payload = make_llm_payload(recommendation="word " * 400)
    with pytest.raises(LLMResponseError, match="exceeding"):
        reason_with(payload, high_risk_evidence)


def test_reasoning_bullets_are_capped(high_risk_evidence) -> None:
    payload = make_llm_payload(reasoning=[f"bullet {index}" for index in range(20)])
    assert len(reason_with(payload, high_risk_evidence).reasoning) == 6


# =========================================================
# 4. GUARDRAILS APPLY TO EVERY PIECE OF MODEL PROSE
# =========================================================


def test_fabricated_offer_in_the_recommendation_is_rejected(high_risk_evidence) -> None:
    payload = make_llm_payload(
        recommendation="Offer this customer 30% off their monthly bill for a year."
    )
    with pytest.raises(GuardrailViolation, match="fabricated_percentage_offer"):
        reason_with(payload, high_risk_evidence)


def test_causal_claim_in_the_reasoning_is_rejected(high_risk_evidence) -> None:
    payload = make_llm_payload(
        reasoning=["The month-to-month contract causes churn for this customer."]
    )
    with pytest.raises(GuardrailViolation, match="causal_claim"):
        reason_with(payload, high_risk_evidence)


def test_claimed_action_is_rejected(high_risk_evidence) -> None:
    payload = make_llm_payload(caveats=["I have contacted the customer already."])
    with pytest.raises(GuardrailViolation, match="claimed_executed_action"):
        reason_with(payload, high_risk_evidence)
