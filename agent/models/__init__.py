"""Typed data contracts used by the retention agent."""

from agent.models.evidence import CustomerEvidence, DriverEvidence
from agent.models.recommendation import (
    ConfidenceLevel,
    RetentionRecommendation,
    SelectedStrategy,
    SupportingEvidence,
)
from agent.models.scenario import Scenario, UnsimulatableIntervention
from agent.models.strategy import RetentionStrategy, StrategyCandidate
from agent.models.whatif import (
    BaselinePrediction,
    DriverDelta,
    DriverSnapshot,
    ScenarioOutcome,
    ScenarioRejection,
    WhatIfResult,
)

__all__ = [
    "BaselinePrediction",
    "ConfidenceLevel",
    "CustomerEvidence",
    "DriverDelta",
    "DriverEvidence",
    "DriverSnapshot",
    "RetentionRecommendation",
    "RetentionStrategy",
    "Scenario",
    "ScenarioOutcome",
    "ScenarioRejection",
    "SelectedStrategy",
    "StrategyCandidate",
    "SupportingEvidence",
    "UnsimulatableIntervention",
    "WhatIfResult",
]
