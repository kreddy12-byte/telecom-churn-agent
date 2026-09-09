"""Agent services: AI reasoning and recommendation orchestration.

``evidence_builder`` is intentionally not re-exported here: importing it pulls in
the ML and SHAP stack, and the reasoning/recommendation layers are designed to
work on evidence objects regardless of where they came from.
"""

from agent.services.reasoning_service import LLMReasoning, ReasoningService
from agent.services.recommendation_service import RecommendationService

__all__ = ["LLMReasoning", "ReasoningService", "RecommendationService"]
