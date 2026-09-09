"""Retention strategy catalogue and evidence-based evaluation."""

from agent.strategies.catalogue import (
    FALLBACK_STRATEGY,
    STRATEGY_CATALOGUE,
    get_catalogue,
    get_strategy,
    valid_strategy_ids,
)
from agent.strategies.evaluator import evaluate_customer

__all__ = [
    "FALLBACK_STRATEGY",
    "STRATEGY_CATALOGUE",
    "evaluate_customer",
    "get_catalogue",
    "get_strategy",
    "valid_strategy_ids",
]
