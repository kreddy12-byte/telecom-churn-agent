"""Strategy catalogue integrity tests."""

from __future__ import annotations

from agent.strategies.catalogue import (
    FALLBACK_STRATEGY,
    STRATEGY_CATALOGUE,
    get_catalogue,
    get_strategy,
    valid_strategy_ids,
)

EXPECTED_STRATEGY_IDS = {
    "CONTRACT_CONVERSION",
    "PRICING_VALUE",
    "SUPPORT_INTERVENTION",
    "SERVICE_BUNDLE_OPTIMIZATION",
    "EARLY_LIFECYCLE_ONBOARDING",
    "GENERAL_RETENTION_REVIEW",
}


def test_catalogue_loads_expected_strategies() -> None:
    assert valid_strategy_ids() == EXPECTED_STRATEGY_IDS
    assert len(get_catalogue()) == len(EXPECTED_STRATEGY_IDS)


def test_strategy_ids_are_unique() -> None:
    ids = [strategy.strategy_id for strategy in STRATEGY_CATALOGUE]
    assert len(ids) == len(set(ids))


def test_every_strategy_has_required_fields() -> None:
    for strategy in STRATEGY_CATALOGUE:
        assert strategy.strategy_id and strategy.strategy_id.isupper()
        assert strategy.name
        assert strategy.description
        assert strategy.objective
        assert strategy.allowed_actions, f"{strategy.strategy_id} has no allowed actions"
        assert strategy.contraindications, f"{strategy.strategy_id} has no contraindications"
        assert strategy.priority >= 1


def test_only_the_escalation_strategy_has_no_risk_drivers() -> None:
    """Every real play must be tied to evidence; only the fallback is generic."""
    for strategy in STRATEGY_CATALOGUE:
        if strategy.is_fallback:
            assert strategy.applicable_risk_drivers == ()
        else:
            assert strategy.applicable_risk_drivers


def test_exactly_one_fallback_strategy() -> None:
    fallbacks = [strategy for strategy in STRATEGY_CATALOGUE if strategy.is_fallback]
    assert fallbacks == [FALLBACK_STRATEGY]


def test_lookup_rejects_unknown_strategy() -> None:
    assert get_strategy("CONTRACT_CONVERSION") is not None
    assert get_strategy("FREE_IPHONE_GIVEAWAY") is None


def test_strategies_are_immutable() -> None:
    """Catalogue entries are frozen so runtime code cannot rewrite business rules."""
    strategy = get_strategy("PRICING_VALUE")
    assert strategy is not None
    try:
        strategy.priority = 1  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("Strategy should be immutable.")
