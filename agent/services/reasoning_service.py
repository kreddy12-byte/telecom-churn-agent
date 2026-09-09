"""Turn the LLM's raw reply into validated reasoning, or reject it.

This layer trusts nothing the model says. It parses the reply, checks the chosen
strategy against the candidates that were actually offered, and runs the safety
guardrails over the prose. Anything that fails raises, and the caller falls back
to the deterministic engine.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from agent.guardrails import GuardrailViolation, assert_no_unsupported_claims
from agent.models.evidence import CustomerEvidence
from agent.models.recommendation import ConfidenceLevel
from agent.models.strategy import StrategyEvaluation
from agent.prompts.retention_prompt import RETENTION_SYSTEM_PROMPT, build_reasoning_prompt
from agent.providers.base import LLMProvider, LLMResponseError
from ml.src.logging_config import get_logger

logger = get_logger(__name__)

MAX_RECOMMENDATION_CHARS = 1200
MAX_REASONING_BULLETS = 6
VALID_CONFIDENCE_VALUES = {"LOW", "MEDIUM", "HIGH"}


@dataclass(frozen=True)
class LLMReasoning:
    """Validated output of the reasoning layer."""

    strategy_id: str
    recommendation: str
    reasoning: list[str]
    claimed_confidence: ConfidenceLevel | None
    caveats: list[str]
    provider_label: str


class ReasoningService:
    """Runs the AI reasoning step over structured ML evidence."""

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    # =========================================================
    # 1. BUILD AI REASONING CONTEXT AND CALL THE MODEL
    # =========================================================

    def generate(
        self, evidence: CustomerEvidence, evaluation: StrategyEvaluation
    ) -> LLMReasoning:
        """Produce validated reasoning for one customer.

        Raises:
            LLMError: provider failures (unavailable, timeout, bad transport).
            LLMResponseError: the reply was malformed or broke a rule.
            GuardrailViolation: the prose contained an unsupported claim.
        """
        user_prompt = build_reasoning_prompt(evidence, evaluation)
        completion = self.provider.complete(RETENTION_SYSTEM_PROMPT, user_prompt)

        payload = self._parse_json(completion.text)
        return self._validate(payload, evaluation, completion.label)

    # =========================================================
    # 2. PARSE THE REPLY
    # =========================================================

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove ```json fences some models add despite being told not to."""
        cleaned = text.strip()
        if not cleaned.startswith("```"):
            return cleaned

        without_opening = cleaned.split("\n", 1)[-1]
        if "```" in without_opening:
            without_opening = without_opening.rsplit("```", 1)[0]
        return without_opening.strip()

    def _parse_json(self, text: str) -> dict:
        """Parse the reply as a JSON object."""
        cleaned = self._strip_code_fences(text)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f"LLM did not return valid JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise LLMResponseError(
                f"LLM returned {type(payload).__name__}, expected a JSON object."
            )
        return payload

    # =========================================================
    # 3. VALIDATE AI OUTPUT
    # =========================================================

    def _validate(
        self, payload: dict, evaluation: StrategyEvaluation, provider_label: str
    ) -> LLMReasoning:
        strategy_id = self._validate_strategy(payload, evaluation)
        recommendation = self._validate_recommendation(payload)
        reasoning = self._validate_reasoning(payload)
        caveats = self._validate_caveats(payload)
        claimed_confidence = self._validate_confidence(payload)

        # The prompt forbids fabricated offers and guarantees; verify it obeyed.
        try:
            assert_no_unsupported_claims(recommendation, *reasoning, *caveats)
        except GuardrailViolation:
            logger.warning("LLM output violated a safety guardrail; discarding it.")
            raise

        return LLMReasoning(
            strategy_id=strategy_id,
            recommendation=recommendation,
            reasoning=reasoning,
            claimed_confidence=claimed_confidence,
            caveats=caveats,
            provider_label=provider_label,
        )

    @staticmethod
    def _validate_strategy(payload: dict, evaluation: StrategyEvaluation) -> str:
        """The model may only pick a strategy that was actually offered.

        Checking against the *candidates* rather than the whole catalogue also
        blocks a technically-valid-but-ineligible play, such as proposing a
        contract conversion to someone already on a two-year contract.
        """
        strategy_id = payload.get("strategy_id")
        if not isinstance(strategy_id, str) or not strategy_id.strip():
            raise LLMResponseError("LLM response is missing 'strategy_id'.")

        strategy_id = strategy_id.strip()
        offered = evaluation.candidate_ids
        if strategy_id not in offered:
            raise LLMResponseError(
                f"LLM chose strategy '{strategy_id}', which was not among the "
                f"candidates offered ({offered})."
            )
        return strategy_id

    @staticmethod
    def _validate_recommendation(payload: dict) -> str:
        recommendation = payload.get("recommendation")
        if not isinstance(recommendation, str) or not recommendation.strip():
            raise LLMResponseError("LLM response is missing 'recommendation' text.")
        if len(recommendation) > MAX_RECOMMENDATION_CHARS:
            raise LLMResponseError(
                f"LLM recommendation is {len(recommendation)} characters, exceeding the "
                f"{MAX_RECOMMENDATION_CHARS}-character limit."
            )
        return recommendation.strip()

    @staticmethod
    def _validate_reasoning(payload: dict) -> list[str]:
        reasoning = payload.get("reasoning", [])
        if isinstance(reasoning, str):  # tolerate a single string
            reasoning = [reasoning]
        if not isinstance(reasoning, list) or not reasoning:
            raise LLMResponseError("LLM response is missing 'reasoning' bullets.")

        bullets = [str(item).strip() for item in reasoning if str(item).strip()]
        if not bullets:
            raise LLMResponseError("LLM 'reasoning' contained no usable bullets.")
        return bullets[:MAX_REASONING_BULLETS]

    @staticmethod
    def _validate_caveats(payload: dict) -> list[str]:
        caveats = payload.get("caveats", [])
        if isinstance(caveats, str):
            caveats = [caveats]
        if not isinstance(caveats, list):
            return []
        return [str(item).strip() for item in caveats if str(item).strip()]

    @staticmethod
    def _validate_confidence(payload: dict) -> ConfidenceLevel | None:
        """Read the model's claimed confidence; treat anything odd as absent.

        The claim is advisory: the recommendation service only ever uses it to
        lower the system's own computed confidence.
        """
        claimed = payload.get("confidence")
        if not isinstance(claimed, str):
            return None
        normalized = claimed.strip().upper()
        return normalized if normalized in VALID_CONFIDENCE_VALUES else None  # type: ignore[return-value]
