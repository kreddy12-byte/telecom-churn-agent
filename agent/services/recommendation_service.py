"""Orchestrates the full retention recommendation flow.

    Customer evidence  →  strategy engine  →  AI reasoning  →  recommendation

The service owns every fact in the output. The LLM contributes only the
recommendation prose and the reasoning bullets; probabilities, SHAP values,
strategy definitions, objectives, confidence, limitations, and the approval flag
are attached by this module. If the LLM is unavailable or produces anything
invalid, the deterministic engine writes the prose instead and says so.
"""

from __future__ import annotations

from agent.confidence import assess_confidence, downgrade_only
from agent.guardrails import GuardrailViolation
from agent.models.evidence import CustomerEvidence, DriverEvidence
from agent.models.recommendation import (
    PROVIDER_DETERMINISTIC,
    STANDARD_LIMITATIONS,
    RetentionRecommendation,
    SelectedStrategy,
    SupportingEvidence,
)
from agent.models.strategy import StrategyCandidate, StrategyEvaluation
from agent.providers.base import LLMError, LLMProvider
from agent.services.reasoning_service import LLMReasoning, ReasoningService
from agent.strategies.evaluator import evaluate_customer
from ml.src.logging_config import get_logger

logger = get_logger(__name__)

# How many drivers are quoted as supporting evidence when the selected strategy
# matched none of them (the escalation case).
FALLBACK_EVIDENCE_DRIVER_COUNT = 3


class RecommendationService:
    """Produces a human-approvable retention recommendation from ML evidence."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        """
        Args:
            provider: Configured LLM provider, or None to run purely
                deterministically. Passing None is a supported production mode,
                not a degraded one — it simply removes the personalisation layer.
        """
        self.provider = provider
        self._reasoning_service = ReasoningService(provider) if provider is not None else None

    # =========================================================
    # 1. ENTRY POINT
    # =========================================================

    def recommend(self, evidence: CustomerEvidence) -> RetentionRecommendation:
        """Generate a recommendation for one customer.

        The evidence object is already validated by Pydantic, so invalid input
        fails before reaching any strategy or LLM logic.
        """
        # --- 2. EVALUATE CUSTOMER EVIDENCE --- #
        evaluation = evaluate_customer(evidence)

        # --- 3. GENERATE RECOMMENDATION (AI reasoning, if available) --- #
        reasoning, fallback_reason = self._try_ai_reasoning(evidence, evaluation)

        # --- 4. APPLY FALLBACK LOGIC --- #
        if reasoning is None:
            return self._build_deterministic_recommendation(
                evidence, evaluation, fallback_reason
            )
        return self._build_ai_recommendation(evidence, evaluation, reasoning)

    # =========================================================
    # 2. AI REASONING WITH GUARANTEED DEGRADATION
    # =========================================================

    def _try_ai_reasoning(
        self, evidence: CustomerEvidence, evaluation: StrategyEvaluation
    ) -> tuple[LLMReasoning | None, str | None]:
        """Attempt LLM reasoning, returning (reasoning, fallback_reason).

        Every failure mode — no provider, missing key, timeout, network error,
        malformed JSON, invalid strategy, guardrail violation — resolves to the
        deterministic path with an explicit, reportable reason. The agent never
        raises an LLM error at the caller.
        """
        if self._reasoning_service is None:
            return None, "No LLM provider is configured; used the deterministic strategy engine."

        if not self.provider.is_available():  # type: ignore[union-attr]
            return None, "The LLM provider is not usable (missing API key or endpoint)."

        try:
            return self._reasoning_service.generate(evidence, evaluation), None
        except GuardrailViolation as exc:
            logger.warning("Discarding LLM output after guardrail violation: %s", exc)
            return None, f"LLM output was rejected by a safety guardrail ({exc})."
        except LLMError as exc:
            logger.warning("LLM reasoning failed (%s): %s", type(exc).__name__, exc)
            return None, f"LLM reasoning failed ({type(exc).__name__}: {exc})."
        except Exception as exc:  # noqa: BLE001 - last-resort safety net
            # A recommendation must always be produced, so an unforeseen provider
            # bug degrades to the deterministic engine rather than failing the
            # request. The reason is surfaced, never swallowed.
            logger.exception("Unexpected error during LLM reasoning.")
            return None, f"Unexpected LLM error ({type(exc).__name__}: {exc})."

    # =========================================================
    # 3. SUPPORTING EVIDENCE (ALWAYS SYSTEM-OWNED)
    # =========================================================

    @staticmethod
    def _build_supporting_evidence(
        evidence: CustomerEvidence, chosen: StrategyCandidate
    ) -> list[SupportingEvidence]:
        """Attach the real SHAP drivers behind the selected strategy.

        Built from the explanation rather than from LLM text, which is what makes
        the numbers in a recommendation impossible to fabricate.
        """
        drivers: tuple[DriverEvidence, ...] | list[DriverEvidence] = chosen.matched_drivers
        if not drivers:
            # Escalation case: show the strongest risk drivers so the human
            # reviewer still sees why the account surfaced.
            drivers = evidence.risk_increasing_drivers[:FALLBACK_EVIDENCE_DRIVER_COUNT]

        return [
            SupportingEvidence(
                feature=driver.feature,
                value=driver.value,
                shap_value=round(driver.shap_value, 4),
                direction=driver.direction,
            )
            for driver in drivers
        ]

    @staticmethod
    def _find_candidate(evaluation: StrategyEvaluation, strategy_id: str) -> StrategyCandidate:
        """Resolve a validated strategy id back to its candidate record."""
        for candidate in evaluation.candidates:
            if candidate.strategy_id == strategy_id:
                return candidate
        # Unreachable: the reasoning service rejects ids outside the candidates.
        raise ValueError(f"Strategy '{strategy_id}' is not among the evaluated candidates.")

    # =========================================================
    # 4. DETERMINISTIC RECOMMENDATION
    # =========================================================

    @staticmethod
    def _deterministic_text(
        evidence: CustomerEvidence, chosen: StrategyCandidate
    ) -> tuple[str, list[str]]:
        """Compose recommendation text from the catalogue and real evidence only.

        Every sentence is assembled from values that exist in the evidence, so the
        deterministic path cannot state a customer fact that was not supplied.
        """
        strategy = chosen.strategy
        lead_action = strategy.allowed_actions[0] if strategy.allowed_actions else strategy.objective

        driver_phrase = ", ".join(
            f"{driver.feature}"
            + (f" ({driver.value})" if driver.value is not None else "")
            for driver in chosen.matched_drivers
        )

        if chosen.matched_drivers:
            recommendation = (
                f"{lead_action} The model places this customer in the {evidence.risk_level} "
                f"risk band with a churn probability of {evidence.churn_probability:.2f}, and "
                f"the strategy targets the risk-increasing driver(s): {driver_phrase}. "
                "A retention specialist must review and approve before any customer contact."
            )
        else:
            recommendation = (
                f"{lead_action} No catalogue strategy matched this customer's risk-increasing "
                f"drivers, so the account needs specialist judgement. The model places the "
                f"customer in the {evidence.risk_level} risk band with a churn probability of "
                f"{evidence.churn_probability:.2f}."
            )

        reasoning = [
            f"The churn model (version {evidence.model_version}) estimates a "
            f"{evidence.churn_probability:.2f} probability of churn, placing this customer in "
            f"the {evidence.risk_level} risk band."
        ]
        for driver in chosen.matched_drivers:
            value_text = f" (customer value: {driver.value})" if driver.value is not None else ""
            reasoning.append(
                f"{driver.feature}{value_text} increases the model's risk estimate and accounts "
                f"for {driver.impact:.0%} of this customer's total SHAP impact."
            )
        if not chosen.matched_drivers:
            reasoning.append(
                "None of the customer's risk-increasing drivers map to a specific retention "
                "strategy in the catalogue."
            )
        reasoning.append(
            f"{strategy.name} was selected because it is the eligible strategy with the "
            f"strongest alignment to that evidence (alignment score "
            f"{chosen.alignment_score:.2f})."
        )
        return recommendation, reasoning

    def _build_deterministic_recommendation(
        self,
        evidence: CustomerEvidence,
        evaluation: StrategyEvaluation,
        fallback_reason: str | None,
    ) -> RetentionRecommendation:
        """Highest-ranked eligible strategy, described without any LLM involvement."""
        chosen = evaluation.best
        recommendation_text, reasoning = self._deterministic_text(evidence, chosen)
        confidence = assess_confidence(evidence, evaluation, selected=chosen)

        limitations = list(STANDARD_LIMITATIONS)
        limitations.append(
            "This recommendation was generated by the deterministic strategy engine, "
            "not by a language model, so the wording is templated rather than personalised."
        )

        return RetentionRecommendation(
            customer_id=evidence.customer_id,
            churn_probability=evidence.churn_probability,
            risk_level=evidence.risk_level,
            model_version=evidence.model_version,
            selected_strategy=SelectedStrategy(
                strategy_id=chosen.strategy.strategy_id,
                strategy_name=chosen.strategy.name,
            ),
            recommendation=recommendation_text,
            reasoning=reasoning,
            supporting_evidence=self._build_supporting_evidence(evidence, chosen),
            objective=chosen.strategy.objective,
            confidence=confidence.level,
            confidence_rationale=confidence.rationale,
            requires_human_approval=True,
            limitations=limitations,
            provider=PROVIDER_DETERMINISTIC,
            fallback_reason=fallback_reason,
            candidate_strategy_ids=evaluation.candidate_ids,
        )

    # =========================================================
    # 5. AI-PERSONALISED RECOMMENDATION
    # =========================================================

    def _build_ai_recommendation(
        self,
        evidence: CustomerEvidence,
        evaluation: StrategyEvaluation,
        reasoning: LLMReasoning,
    ) -> RetentionRecommendation:
        """Combine validated LLM prose with system-owned facts."""
        chosen = self._find_candidate(evaluation, reasoning.strategy_id)

        # Confidence is computed by the system; the model may only lower it.
        computed = assess_confidence(evidence, evaluation, selected=chosen)
        final_confidence = downgrade_only(computed.level, reasoning.claimed_confidence)

        confidence_rationale = computed.rationale
        if final_confidence != computed.level:
            confidence_rationale += (
                f" Lowered from {computed.level} to {final_confidence} because the reasoning "
                "model reported lower confidence."
            )

        limitations = list(STANDARD_LIMITATIONS)
        limitations.append(
            "The recommendation wording was generated by a language model from the evidence "
            "above; the evidence, strategy, and confidence were computed by the system."
        )
        limitations.extend(reasoning.caveats)

        return RetentionRecommendation(
            customer_id=evidence.customer_id,
            churn_probability=evidence.churn_probability,
            risk_level=evidence.risk_level,
            model_version=evidence.model_version,
            selected_strategy=SelectedStrategy(
                strategy_id=chosen.strategy.strategy_id,
                strategy_name=chosen.strategy.name,
            ),
            recommendation=reasoning.recommendation,
            reasoning=reasoning.reasoning,
            supporting_evidence=self._build_supporting_evidence(evidence, chosen),
            # Objective comes from the catalogue, never from the model, so the
            # stated intent of an intervention is always business-approved.
            objective=chosen.strategy.objective,
            confidence=final_confidence,
            confidence_rationale=confidence_rationale,
            requires_human_approval=True,
            limitations=limitations,
            provider=reasoning.provider_label,
            fallback_reason=None,
            candidate_strategy_ids=evaluation.candidate_ids,
        )
