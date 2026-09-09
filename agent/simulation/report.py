"""Human-readable rendering of a what-if analysis."""

from __future__ import annotations

from agent.models.recommendation import PROVIDER_DETERMINISTIC
from agent.models.whatif import ScenarioOutcome, WhatIfResult

SEPARATOR = "=" * 78
SUB_SEPARATOR = "-" * 50


def _format_drivers(outcome: ScenarioOutcome) -> list[str]:
    """Side-by-side SHAP comparison, so the reader sees *why* the estimate moved."""
    lines = [
        f"  {'feature':<18} {'baseline':>10} {'scenario':>10} {'change':>10}",
    ]
    for delta in outcome.driver_deltas:
        marker = " *" if delta.changed_by_scenario else "  "
        lines.append(
            f"  {delta.feature:<18} {delta.baseline_shap:>+10.4f} "
            f"{delta.scenario_shap:>+10.4f} {delta.shap_change:>+10.4f}{marker}"
        )
    lines.append("  (* = feature changed by the scenario)")
    return lines


def render_whatif_report(result: WhatIfResult) -> str:
    """Format a complete what-if analysis for a terminal reader."""
    lines: list[str] = []

    def heading(title: str) -> None:
        lines.append("")
        lines.append(title)
        lines.append("-" * len(title))

    lines.append(SEPARATOR)
    lines.append("WHAT-IF RETENTION SIMULATION")
    lines.append(SEPARATOR)
    lines.append("Model-based what-if estimate — not a causal prediction.")

    heading("CUSTOMER")
    lines.append(f"  Customer ID   : {result.customer_id}")
    lines.append(f"  Model version : {result.baseline.model_version}")

    heading("BASELINE")
    lines.append(
        f"  {result.baseline.churn_probability:.2%} {result.baseline.risk_level} "
        f"(predicted class {result.baseline.prediction})"
    )
    for driver in result.baseline.top_drivers:
        lines.append(
            f"    {driver.feature:<18} value={str(driver.value):<16} "
            f"shap={driver.shap_value:+.4f}  {driver.direction}"
        )

    # --- Scenarios, in ranked order --- #
    for index, outcome in enumerate(result.scenarios, start=1):
        lines.append("")
        lines.append(SUB_SEPARATOR)
        lines.append(f"SCENARIO {index}")
        lines.append(SUB_SEPARATOR)
        lines.append(f"  Name             : {outcome.scenario_name} ({outcome.scenario_id})")
        lines.append(f"  Strategy         : {outcome.strategy_id}")
        lines.append(f"  Changed features : {outcome.changed_features}")
        lines.append(
            f"  Model estimate   : {outcome.baseline_probability:.2%} -> "
            f"{outcome.scenario_probability:.2%} "
            f"({outcome.percentage_point_change:+.2f} percentage points)"
        )
        lines.append(
            f"  Risk             : {outcome.baseline_risk_level} -> "
            f"{outcome.scenario_risk_level}"
            + ("  (band changed)" if outcome.risk_level_changed else "")
        )
        factors = outcome.ranking_factors
        lines.append(
            f"  Ranking score    : {outcome.ranking_score:.4f} "
            f"(model_response {factors.model_response:.2f}, "
            f"evidence_alignment {factors.evidence_alignment:.2f}, "
            f"driver_targeting {factors.driver_targeting:.2f}"
            + (", conflict penalty applied" if factors.conflict_penalty_applied else "")
            + ")"
        )
        if outcome.conflict_reason:
            lines.append(f"  Evidence conflict: {outcome.conflict_reason}")
        lines.append("  Largest SHAP movements:")
        lines.extend(_format_drivers(outcome))
        lines.append(f"  Interpretation   : {outcome.model_based_interpretation}")

    if result.rejected_scenarios:
        heading("SCENARIOS NOT APPLICABLE TO THIS CUSTOMER")
        for rejection in result.rejected_scenarios:
            lines.append(f"  - {rejection.scenario_id}: {rejection.reason}")

    if result.unsimulatable_interventions:
        heading("INTERVENTIONS THAT CANNOT BE SIMULATED")
        for item in result.unsimulatable_interventions:
            lines.append(f"  - [{item.strategy_id}] {item.intervention}")
            lines.append(f"    {item.reason}")

    lines.append("")
    lines.append(SEPARATOR)
    lines.append("SCENARIO COMPARISON")
    lines.append(SEPARATOR)
    lines.append(f"  {'rank':<5} {'scenario':<32} {'estimate':>10} {'change':>9} {'score':>7}")
    for rank, outcome in enumerate(result.scenarios, start=1):
        lines.append(
            f"  {rank:<5} {outcome.scenario_id:<32} "
            f"{outcome.scenario_probability:>9.2%} "
            f"{outcome.percentage_point_change:>+8.2f}pp {outcome.ranking_score:>7.4f}"
        )
    lines.append("")
    lines.append(f"  Ranking methodology: {result.ranking_methodology}")

    heading("RECOMMENDED SCENARIO")
    lines.append(f"  {result.recommended_scenario_id or 'none'}")
    lines.append(f"  {result.selection_reason}")

    lines.append("")
    lines.append(SEPARATOR)
    lines.append("AI INTERPRETATION")
    lines.append(SEPARATOR)
    generated_by = (
        "deterministic engine (no LLM)"
        if result.provider == PROVIDER_DETERMINISTIC
        else f"LLM provider '{result.provider}'"
    )
    lines.append(f"  [generated by: {generated_by}]")
    if result.fallback_reason:
        lines.append(f"  [fallback reason: {result.fallback_reason}]")
    lines.append(f"  {result.ai_interpretation}")
    if result.ai_alternative_scenario_id:
        lines.append(
            f"  Note: the reasoning model read '{result.ai_alternative_scenario_id}' as most "
            "promising, which differs from the system ranking."
        )

    heading("CONSIDERATIONS FOR THE REVIEWER")
    for consideration in result.ai_considerations:
        lines.append(f"  - {consideration}")

    heading("LIMITATIONS")
    for limitation in result.limitations:
        lines.append(f"  - {limitation}")

    heading("HUMAN APPROVAL REQUIRED")
    lines.append(f"  {result.requires_human_approval}")

    lines.append("")
    lines.append(SEPARATOR)
    return "\n".join(lines)
