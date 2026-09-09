"""AI interpretation of what-if results — all with mocked provider responses."""

from __future__ import annotations

import json

import pytest

from agent.models.recommendation import PROVIDER_DETERMINISTIC
from agent.prompts.whatif_prompt import WHATIF_SYSTEM_PROMPT, build_whatif_prompt
from agent.providers.base import LLMTimeoutError, LLMUnavailableError
from agent.services.scenario_interpretation_service import ScenarioInterpretationService
from agent.tests.conftest import StubProvider

VALID_INTERPRETATION = (
    "The trained model places this customer in the HIGH risk band. Under the two-year "
    "contract profile the model estimates a lower churn probability, and contract type is "
    "among the drivers the explanation highlights. Treat this as model sensitivity rather "
    "than an expected outcome."
)


def make_payload(
    scenario_id: str | None = "two_year_contract",
    interpretation: str = VALID_INTERPRETATION,
    considerations: list[str] | None = None,
    caveats: list[str] | None = None,
    **extra,
) -> str:
    payload: dict = {
        "most_promising_scenario_id": scenario_id,
        "interpretation": interpretation,
        "considerations": considerations
        or [
            "Confirm a two-year contract is something this customer can be offered.",
            "The estimate assumes no other change to the customer's profile.",
        ],
    }
    if caveats is not None:
        payload["caveats"] = caveats
    payload.update(extra)
    return json.dumps(payload)


def interpret(provider, result):
    return ScenarioInterpretationService(provider=provider).interpret(result)


# =========================================================
# 1. PROMPT CONTENT
# =========================================================


def test_prompt_carries_the_finished_results(whatif_result) -> None:
    payload = json.loads(build_whatif_prompt(whatif_result))

    assert payload["baseline_prediction"]["churn_probability"] == 0.8064
    assert [s["scenario_id"] for s in payload["scenario_results"]] == [
        "two_year_contract",
        "annual_contract",
    ]
    assert payload["system_ranking"]["recommended_scenario_id"] == "two_year_contract"
    assert payload["scenario_results"][0]["ranking_factors"]["model_response"] == 0.2


def test_system_prompt_forbids_causal_framing() -> None:
    for phrase in ["reduces churn", "prevents churn", "human approval", "JSON"]:
        assert phrase in WHATIF_SYSTEM_PROMPT


# =========================================================
# 2. HAPPY PATH
# =========================================================


def test_valid_interpretation_is_used(whatif_result) -> None:
    result = interpret(StubProvider(response_text=make_payload()), whatif_result)

    assert result.provider == "stub:stub-model"
    assert result.fallback_reason is None
    assert result.ai_interpretation == VALID_INTERPRETATION
    assert len(result.ai_considerations) == 2
    assert result.generated_by_llm is True


def test_agreement_with_the_ranking_records_no_alternative(whatif_result) -> None:
    result = interpret(
        StubProvider(response_text=make_payload(scenario_id="two_year_contract")), whatif_result
    )
    assert result.ai_alternative_scenario_id is None


def test_disagreement_is_recorded_without_overriding_the_ranking(whatif_result) -> None:
    """The AI may read the results differently; it cannot change the selection."""
    result = interpret(
        StubProvider(response_text=make_payload(scenario_id="annual_contract")), whatif_result
    )

    assert result.recommended_scenario_id == "two_year_contract"
    assert result.ai_alternative_scenario_id == "annual_contract"


def test_considerations_are_capped(whatif_result) -> None:
    payload = make_payload(considerations=[f"point {index}" for index in range(20)])
    result = interpret(StubProvider(response_text=payload), whatif_result)

    assert len(result.ai_considerations) == 5


def test_model_caveats_are_appended_to_limitations(whatif_result) -> None:
    payload = make_payload(caveats=["The customer's billing history was not supplied."])
    result = interpret(StubProvider(response_text=payload), whatif_result)

    assert "The customer's billing history was not supplied." in result.limitations


# =========================================================
# 3. THE AI CANNOT TOUCH SYSTEM-OWNED FACTS
# =========================================================


def test_ai_cannot_change_probabilities_or_shap_values(whatif_result) -> None:
    """Even when the reply contains its own numbers, the result keeps the real ones."""
    payload = make_payload(
        churn_probability=0.05,
        scenarios=[{"scenario_id": "two_year_contract", "scenario_probability": 0.01}],
        baseline={"churn_probability": 0.05},
    )
    result = interpret(StubProvider(response_text=payload), whatif_result)

    assert result.baseline.churn_probability == 0.8064
    assert result.baseline.top_drivers[0].shap_value == 1.3752
    assert result.scenarios[0].scenario_probability == 0.4984
    assert result.scenarios[0].ranking_score == 0.2320


def test_ai_cannot_invent_a_scenario(whatif_result) -> None:
    payload = make_payload(scenario_id="free_upgrade_forever")
    result = interpret(StubProvider(response_text=payload), whatif_result)

    assert result.provider == PROVIDER_DETERMINISTIC
    assert result.fallback_reason is not None
    assert "was not simulated" in result.fallback_reason


def test_ai_cannot_remove_the_approval_requirement(whatif_result) -> None:
    payload = make_payload(requires_human_approval=False)
    result = interpret(StubProvider(response_text=payload), whatif_result)

    assert result.requires_human_approval is True


# =========================================================
# 4. CAUSAL LANGUAGE IS REJECTED
# =========================================================


@pytest.mark.parametrize(
    "interpretation",
    [
        "Moving to a two-year contract will reduce churn for this customer.",
        "This scenario delivers a 30% churn reduction.",
        "A longer contract prevents churn in cases like this.",
    ],
)
def test_causal_claims_trigger_the_deterministic_fallback(interpretation, whatif_result) -> None:
    payload = make_payload(interpretation=interpretation)
    result = interpret(StubProvider(response_text=payload), whatif_result)

    assert result.provider == PROVIDER_DETERMINISTIC
    assert result.fallback_reason is not None
    assert "safety guardrail" in result.fallback_reason


def test_causal_claim_in_a_consideration_is_also_caught(whatif_result) -> None:
    payload = make_payload(considerations=["This intervention will prevent churn."])
    result = interpret(StubProvider(response_text=payload), whatif_result)

    assert result.provider == PROVIDER_DETERMINISTIC


def test_correct_model_estimate_phrasing_is_accepted(whatif_result) -> None:
    """The allowed wording must not be caught by the guardrail."""
    payload = make_payload(
        interpretation=(
            "Under this hypothetical profile the trained model estimates a lower churn "
            "probability than the baseline."
        )
    )
    result = interpret(StubProvider(response_text=payload), whatif_result)

    assert result.generated_by_llm is True


# =========================================================
# 5. FALLBACK PATHS
# =========================================================


@pytest.mark.parametrize(
    ("provider", "expected_fragment"),
    [
        (None, "No LLM provider is configured"),
        (StubProvider(available=False), "not usable"),
        (StubProvider(error=LLMTimeoutError("timed out")), "LLMTimeoutError"),
        (StubProvider(error=LLMUnavailableError("no route")), "LLMUnavailableError"),
        (StubProvider(response_text="not json"), "LLMResponseError"),
        (StubProvider(response_text=json.dumps({"considerations": []})), "LLMResponseError"),
        (StubProvider(error=RuntimeError("provider bug")), "Unexpected LLM error"),
    ],
)
def test_failures_fall_back_to_the_deterministic_interpretation(
    provider, expected_fragment: str, whatif_result
) -> None:
    result = interpret(provider, whatif_result)

    assert result.provider == PROVIDER_DETERMINISTIC
    assert result.fallback_reason is not None
    assert expected_fragment in result.fallback_reason
    assert result.ai_interpretation  # a usable interpretation is still produced
    assert result.requires_human_approval is True


def test_deterministic_interpretation_quotes_only_system_values(whatif_result) -> None:
    result = interpret(None, whatif_result)

    assert "80.64%" in result.ai_interpretation
    assert any("deterministic engine" in item for item in result.limitations)
    assert result.ai_considerations


def test_deterministic_interpretation_handles_no_recommendation(whatif_result) -> None:
    empty = whatif_result.model_copy(
        update={
            "scenarios": [],
            "recommended_scenario_id": None,
            "selection_reason": "No scenario in the catalogue applies to this customer's profile.",
        }
    )
    result = interpret(None, empty)

    assert result.ai_interpretation
    assert "No scenario in the catalogue applies" in result.ai_interpretation
