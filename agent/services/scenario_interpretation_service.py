"""AI interpretation of completed what-if results.

# =========================================================
# 1. WHAT THE AI IS AND IS NOT ALLOWED TO DO
# =========================================================

By the time this service runs, every scenario has been simulated, scored, and
ranked. The AI adds prose: what the results mean, whether they line up with the
customer's risk drivers, and what the human reviewer should check.

It cannot change a probability, a SHAP value, a ranking score, or the system's
recommended scenario. If it reads a different scenario as most promising, that
disagreement is recorded in ``ai_alternative_scenario_id`` for the human to
consider — it never overwrites the ranking.

Any failure (no provider, timeout, invalid JSON, unknown scenario, causal
language) falls back to a deterministic interpretation written from the system's
own ranking, labelled as such.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from agent.guardrails import GuardrailViolation, assert_no_unsupported_claims
from agent.models.recommendation import PROVIDER_DETERMINISTIC
from agent.models.whatif import WhatIfResult
from agent.prompts.whatif_prompt import WHATIF_SYSTEM_PROMPT, build_whatif_prompt
from agent.providers.base import LLMError, LLMProvider, LLMResponseError
from ml.src.logging_config import get_logger

logger = get_logger(__name__)

MAX_INTERPRETATION_CHARS = 1500
MAX_CONSIDERATIONS = 5


@dataclass(frozen=True)
class ScenarioInterpretation:
    """Validated prose from the reasoning model."""

    interpretation: str
    considerations: list[str]
    most_promising_scenario_id: str | None
    caveats: list[str] = field(default_factory=list)
    provider_label: str = PROVIDER_DETERMINISTIC


class ScenarioInterpretationService:
    """Adds an AI reading of the simulation, with deterministic fallback."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider

    # =========================================================
    # 2. ENTRY POINT
    # =========================================================

    def interpret(self, result: WhatIfResult) -> WhatIfResult:
        """Return a copy of ``result`` with the interpretation fields filled in.

        A copy rather than an in-place update, so the deterministic simulation
        output remains available unchanged to any caller holding it.
        """
        interpretation, fallback_reason = self._try_ai_interpretation(result)

        if interpretation is None:
            interpretation = self._deterministic_interpretation(result)

        # The AI's pick is recorded only when it differs from the system's; the
        # ranking itself is never overwritten.
        alternative = interpretation.most_promising_scenario_id
        if alternative == result.recommended_scenario_id:
            alternative = None

        return result.model_copy(
            update={
                "ai_interpretation": interpretation.interpretation,
                "ai_considerations": interpretation.considerations,
                "ai_alternative_scenario_id": alternative,
                "provider": interpretation.provider_label,
                "fallback_reason": fallback_reason,
                "limitations": result.limitations + interpretation.caveats,
            }
        )

    # =========================================================
    # 3. CALL THE MODEL, DEGRADE ON ANY FAILURE
    # =========================================================

    def _try_ai_interpretation(
        self, result: WhatIfResult
    ) -> tuple[ScenarioInterpretation | None, str | None]:
        if self.provider is None:
            return None, "No LLM provider is configured; used the deterministic interpretation."

        if not self.provider.is_available():
            return None, "The LLM provider is not usable (missing API key or endpoint)."

        try:
            completion = self.provider.complete(
                WHATIF_SYSTEM_PROMPT, build_whatif_prompt(result)
            )
            payload = self._parse_json(completion.text)
            return self._validate(payload, result, completion.label), None
        except GuardrailViolation as exc:
            logger.warning("Discarding what-if interpretation after guardrail violation: %s", exc)
            return None, f"LLM interpretation was rejected by a safety guardrail ({exc})."
        except LLMError as exc:
            logger.warning("What-if interpretation failed (%s): %s", type(exc).__name__, exc)
            return None, f"LLM interpretation failed ({type(exc).__name__}: {exc})."
        except Exception as exc:  # noqa: BLE001 - last-resort safety net
            logger.exception("Unexpected error during what-if interpretation.")
            return None, f"Unexpected LLM error ({type(exc).__name__}: {exc})."

    # =========================================================
    # 4. PARSE AND VALIDATE
    # =========================================================

    @staticmethod
    def _parse_json(text: str) -> dict:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            if "```" in cleaned:
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f"LLM did not return valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise LLMResponseError(
                f"LLM returned {type(payload).__name__}, expected a JSON object."
            )
        return payload

    def _validate(
        self, payload: dict, result: WhatIfResult, provider_label: str
    ) -> ScenarioInterpretation:
        interpretation = payload.get("interpretation")
        if not isinstance(interpretation, str) or not interpretation.strip():
            raise LLMResponseError("LLM response is missing 'interpretation' text.")
        if len(interpretation) > MAX_INTERPRETATION_CHARS:
            raise LLMResponseError(
                f"Interpretation is {len(interpretation)} characters, exceeding the "
                f"{MAX_INTERPRETATION_CHARS}-character limit."
            )

        considerations = self._string_list(payload.get("considerations"))[:MAX_CONSIDERATIONS]
        caveats = self._string_list(payload.get("caveats"))

        # A scenario the system never simulated cannot be endorsed.
        scenario_id = payload.get("most_promising_scenario_id")
        if scenario_id is not None:
            simulated_ids = [outcome.scenario_id for outcome in result.scenarios]
            if not isinstance(scenario_id, str) or scenario_id not in simulated_ids:
                raise LLMResponseError(
                    f"LLM named scenario '{scenario_id}', which was not simulated "
                    f"(available: {simulated_ids})."
                )

        # Verify the model did not slip into causal or fabricated language.
        assert_no_unsupported_claims(interpretation.strip(), *considerations, *caveats)

        return ScenarioInterpretation(
            interpretation=interpretation.strip(),
            considerations=considerations,
            most_promising_scenario_id=scenario_id,
            caveats=caveats,
            provider_label=provider_label,
        )

    @staticmethod
    def _string_list(value: object) -> list[str]:
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    # =========================================================
    # 5. DETERMINISTIC INTERPRETATION
    # =========================================================

    @staticmethod
    def _deterministic_interpretation(result: WhatIfResult) -> ScenarioInterpretation:
        """Describe the results using only the system's own computed values."""
        recommended = result.recommended_scenario

        if recommended is None:
            summary = (
                f"The trained model estimates a churn probability of "
                f"{result.baseline.churn_probability:.2%} ({result.baseline.risk_level}) for "
                f"this customer. {result.selection_reason}"
            )
        else:
            summary = (
                f"The trained model estimates a churn probability of "
                f"{result.baseline.churn_probability:.2%} ({result.baseline.risk_level}) for "
                f"this customer. {recommended.model_based_interpretation} "
                f"{result.selection_reason}"
            )

        considerations = [
            "These are model-based estimates of sensitivity to hypothetical feature values, "
            "not predictions of what an intervention would achieve.",
            "Confirm the hypothetical profile is something the business can actually offer "
            "this customer.",
        ]
        if result.unsimulatable_interventions:
            considerations.append(
                "Some relevant interventions cannot be simulated at all with the current "
                "model features; see the unsimulatable list before comparing options."
            )
        if any(outcome.conflicts_with_evidence for outcome in result.scenarios):
            considerations.append(
                "At least one scenario changes a feature that currently lowers this "
                "customer's risk estimate; review those before acting."
            )

        return ScenarioInterpretation(
            interpretation=summary,
            considerations=considerations,
            most_promising_scenario_id=result.recommended_scenario_id,
            caveats=[
                "This interpretation was generated by the deterministic engine, not by a "
                "language model, so the wording is templated rather than personalised."
            ],
            provider_label=PROVIDER_DETERMINISTIC,
        )
