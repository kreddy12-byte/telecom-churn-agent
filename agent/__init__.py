"""AI Retention Intelligence layer.

Pipeline position:

    ML prediction -> SHAP explanation -> [ agent ] -> human approval

The agent reasons *over* model evidence. It selects from a controlled catalogue
of retention strategies, uses an LLM only to personalise the wording, and always
returns a recommendation that requires human approval.

Submodules are imported explicitly (``from agent.services.recommendation_service
import RecommendationService``) so that using the strategy engine does not drag
in the ML/SHAP stack.
"""

__all__: list[str] = []
