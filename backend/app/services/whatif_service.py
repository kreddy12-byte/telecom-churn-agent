"""What-if simulation for a stored customer.

Every number the endpoint returns — baseline, scenario probabilities, SHAP
comparisons, ranking scores — is produced by the locked Step 5 engine. This
module resolves the request into validated scenario objects and passes them
through; it contains no simulation logic and defines no thresholds.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from agent.models.scenario import Scenario
from agent.models.whatif import WhatIfResult
from agent.providers.base import LLMProvider
from agent.services.whatif_service import run_whatif_analysis
from agent.simulation.catalogue import build_custom_scenario, get_scenario, valid_scenario_ids
from app.core.errors import InvalidScenarioError, SimulationFailedError
from app.core.logging import get_logger
from app.schemas.whatif import CustomScenarioRequest, WhatIfRequest
from app.services import customer_service
from app.services.ml_runtime import models_dir, translate_ml_errors

logger = get_logger(__name__)


# =========================================================
# 1. RESOLVE REQUESTED SCENARIOS
# =========================================================


def _resolve_catalogue_scenarios(scenario_ids: Sequence[str]) -> list[Scenario]:
    """Look up catalogue scenarios by id.

    An unknown id is rejected outright rather than silently ignored: the caller
    asked for something that does not exist, and returning results for the other
    scenarios would hide the mistake.
    """
    resolved: list[Scenario] = []
    unknown: list[str] = []

    for scenario_id in scenario_ids:
        scenario = get_scenario(scenario_id)
        if scenario is None:
            unknown.append(scenario_id)
        else:
            resolved.append(scenario)

    if unknown:
        raise InvalidScenarioError(
            f"Unknown scenario id(s): {sorted(unknown)}.",
            {"unknown_scenario_ids": sorted(unknown), "valid_scenario_ids": sorted(valid_scenario_ids())},
        )
    return resolved


def _build_custom_scenarios(requests: Sequence[CustomScenarioRequest]) -> list[Scenario]:
    """Turn caller-supplied scenario definitions into Scenario objects.

    These are only *constructed* here. Their feature names and values are checked
    by the simulator's own validator, exactly as catalogue scenarios are.
    """
    scenarios: list[Scenario] = []
    for request in requests:
        try:
            scenarios.append(
                build_custom_scenario(
                    scenario_id=request.scenario_id,
                    scenario_name=request.scenario_name,
                    changed_features=request.changed_features,
                    strategy_id=request.strategy_id,
                    rationale=request.rationale,
                    description=request.description,
                )
            )
        except ValueError as exc:
            raise InvalidScenarioError(
                f"Custom scenario '{request.scenario_id}' is not valid: {exc}",
                {"scenario_id": request.scenario_id},
            ) from exc
    return scenarios


def resolve_scenarios(request: WhatIfRequest) -> list[Scenario] | None:
    """Build the scenario list for a request, or None to use the full catalogue."""
    if request.scenario_ids is None and not request.custom_scenarios:
        return None

    scenarios = _resolve_catalogue_scenarios(request.scenario_ids or [])
    scenarios.extend(_build_custom_scenarios(request.custom_scenarios))

    if not scenarios:
        raise InvalidScenarioError("No scenarios were requested.")
    return scenarios


# =========================================================
# 2. RUN THE SIMULATION
# =========================================================


def simulate_for_customer(
    session: Session, request: WhatIfRequest, provider: LLMProvider | None = None
) -> WhatIfResult:
    """Run the what-if analysis for a stored customer.

    The AI interpretation step is optional and never authoritative: with
    ``use_llm=False`` — or with no LLM configured — the deterministic
    interpretation is used and the result says so.
    """
    record = customer_service.get_customer_record(session, request.customer_id)
    scenarios = resolve_scenarios(request)
    effective_provider = provider if request.use_llm else None

    with translate_ml_errors("Simulation", SimulationFailedError):
        result = run_whatif_analysis(
            record,
            provider=effective_provider,
            scenarios=scenarios,
            models_dir=models_dir(),
        )

    logger.info(
        "What-if for %s: %d scenario(s) evaluated, %d rejected, recommended=%s",
        request.customer_id,
        len(result.scenarios),
        len(result.rejected_scenarios),
        result.recommended_scenario_id,
    )
    return result
