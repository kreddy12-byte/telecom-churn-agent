"""End-to-end what-if analysis: simulate, rank, then interpret.

Thin orchestration on purpose. The deterministic engine
(``compare_retention_scenarios``) and the AI reading
(``ScenarioInterpretationService``) are independently usable and independently
testable; this just runs them in order.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from agent.models.scenario import Scenario
from agent.models.whatif import WhatIfResult
from agent.providers.base import LLMProvider
from agent.services.scenario_interpretation_service import ScenarioInterpretationService
from agent.simulation.comparison import compare_retention_scenarios
from ml.src.prediction.predictor import load_customer_from_dataset


def run_whatif_analysis(
    customer_data: Mapping[str, Any],
    provider: LLMProvider | None = None,
    scenarios: Sequence[Scenario] | None = None,
    models_dir: Path | str | None = None,
) -> WhatIfResult:
    """Simulate every applicable scenario for a customer and interpret the results.

    Args:
        customer_data: The customer's real record.
        provider: LLM provider for the interpretation step. ``None`` uses the
            deterministic interpretation, which is a supported mode.
        scenarios: Scenarios to evaluate; defaults to the approved catalogue.
        models_dir: Override for the model artifact directory (used by tests).
    """
    result = compare_retention_scenarios(
        customer_data, scenarios=scenarios, models_dir=models_dir
    )
    return ScenarioInterpretationService(provider=provider).interpret(result)


def run_whatif_analysis_for_dataset_customer(
    customer_id: str,
    provider: LLMProvider | None = None,
    scenarios: Sequence[Scenario] | None = None,
    models_dir: Path | str | None = None,
) -> WhatIfResult:
    """Look a customer up in the raw dataset and run the full analysis.

    Used for local verification and demos; the backend will pass records from the
    database instead.
    """
    customer_data = load_customer_from_dataset(row=None, customer_id=customer_id)
    return run_whatif_analysis(
        customer_data, provider=provider, scenarios=scenarios, models_dir=models_dir
    )
