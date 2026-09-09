"""What-if retention simulator and strategy comparison engine.

Evaluates how the *existing* trained model responds to hypothetical customer
profiles. Nothing here retrains, and nothing here claims causality.
"""

from agent.simulation.catalogue import (
    SCENARIO_CATALOGUE,
    UNSIMULATABLE_INTERVENTIONS,
    build_custom_scenario,
    get_scenario,
    get_scenario_catalogue,
    scenarios_for_strategy,
    valid_scenario_ids,
)
from agent.simulation.comparison import compare_retention_scenarios, select_recommended_scenario
from agent.simulation.feature_domain import FeatureDomain, check_profile_consistency, domain_for
from agent.simulation.ranking import RANKING_METHODOLOGY, score_scenario
from agent.simulation.simulator import ScenarioSimulation, WhatIfSimulator
from agent.simulation.validator import ScenarioValidationError, build_hypothetical_profile

__all__ = [
    "FeatureDomain",
    "RANKING_METHODOLOGY",
    "SCENARIO_CATALOGUE",
    "ScenarioSimulation",
    "ScenarioValidationError",
    "UNSIMULATABLE_INTERVENTIONS",
    "WhatIfSimulator",
    "build_custom_scenario",
    "build_hypothetical_profile",
    "check_profile_consistency",
    "compare_retention_scenarios",
    "domain_for",
    "get_scenario",
    "get_scenario_catalogue",
    "scenarios_for_strategy",
    "score_scenario",
    "select_recommended_scenario",
    "valid_scenario_ids",
]
