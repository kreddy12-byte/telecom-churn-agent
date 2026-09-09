import { featureLabel, formatPercent, formatPoints, strategyLabel } from "../../utils/format";
import ShapComparison from "./ShapComparison";
import RiskBadge from "../common/RiskBadge";

export default function WhatIfPanel({
  result,
  loading,
  error,
  selectedId,
  onSelect,
}) {
  if (loading) {
    return (
      <p className="muted" role="status">
        Loading what-if scenarios…
      </p>
    );
  }
  if (error) {
    return <p className="text-sm text-rose-800">{error}</p>;
  }
  if (!result) {
    return <p className="muted">No what-if scenarios are available yet.</p>;
  }

  const selected =
    result.scenarios.find((scenario) => scenario.scenario_id === selectedId) ||
    result.scenarios[0];
  const maxProb = Math.max(
    result.baseline.churn_probability,
    ...result.scenarios.map((scenario) => scenario.scenario_probability)
  );

  return (
    <div className="space-y-5">
      <p className="rounded-panel border border-line bg-slate-50 px-3 py-2 text-xs text-ink-muted">
        Model-based what-if estimate — not a causal prediction.
      </p>

      {selected ? (
        <div className="grid gap-2 sm:grid-cols-4">
          <div className="border border-line px-3 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
              Current
            </p>
            <p className="mt-1 text-xl font-semibold tabular-nums">
              {formatPercent(result.baseline.churn_probability)}
            </p>
            <div className="mt-2">
              <RiskBadge level={result.baseline.risk_level} />
            </div>
          </div>
          <div className="border border-line px-3 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
              Scenario
            </p>
            <p className="mt-1 text-sm font-semibold leading-5 text-ink">
              {selected.scenario_name}
            </p>
          </div>
          <div className="border border-line px-3 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
              Hypothetical
            </p>
            <p className="mt-1 text-xl font-semibold tabular-nums">
              {formatPercent(selected.scenario_probability)}
            </p>
            <div className="mt-2">
              <RiskBadge level={selected.scenario_risk_level} />
            </div>
          </div>
          <div className="border border-line px-3 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
              Change
            </p>
            <p className="mt-1 text-xl font-semibold tabular-nums">
              {formatPoints(selected.absolute_probability_change)}
            </p>
            <p className="mt-2 text-xs text-ink-muted">
              {selected.baseline_risk_level} → {selected.scenario_risk_level}
            </p>
          </div>
        </div>
      ) : null}

      <div>
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
          Available interventions
        </p>
        {result.selection_reason ? (
          <p className="mb-3 text-sm text-ink-muted">
            Why it was considered: {result.selection_reason}
          </p>
        ) : null}
        <div className="space-y-2">
          {result.scenarios.map((scenario) => {
            const active = selected?.scenario_id === scenario.scenario_id;
            const recommended = scenario.scenario_id === result.recommended_scenario_id;
            return (
              <button
                key={scenario.scenario_id}
                type="button"
                onClick={() => onSelect(scenario.scenario_id)}
                className={`block w-full rounded-panel border px-3 py-2 text-left ${
                  active ? "border-accent bg-accent-soft" : "border-line bg-white hover:bg-slate-50"
                }`}
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="text-sm font-medium text-ink">
                    {scenario.scenario_name}
                    {recommended ? (
                      <span className="ml-2 text-xs font-semibold text-accent">Selected by ranking</span>
                    ) : null}
                  </span>
                  <span className="text-sm tabular-nums text-ink">
                    {formatPercent(scenario.scenario_probability)}{" "}
                    <span className="text-ink-muted">
                      {formatPoints(scenario.absolute_probability_change)}
                    </span>
                  </span>
                </div>
                {scenario.description ? (
                  <p className="mt-1 text-xs text-ink-muted">{scenario.description}</p>
                ) : null}
                <div className="mt-2 h-1.5 bg-slate-100">
                  <div
                    className="h-1.5 bg-accent"
                    style={{
                      width: `${(scenario.scenario_probability / maxProb) * 100}%`,
                    }}
                  />
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {result.rejected_scenarios?.length ? (
        <p className="text-xs text-ink-muted">
          Not applicable:{" "}
          {result.rejected_scenarios
            .map((item) => item.scenario_name || strategyLabel(item.scenario_id))
            .join(", ")}
          .
        </p>
      ) : null}

      {selected ? (
        <div className="border border-line px-4 py-4">
          <h3 className="text-sm font-semibold text-ink">{selected.scenario_name}</h3>
          <p className="mt-1 text-sm text-ink-muted">{selected.description}</p>
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-ink-faint">Current probability</dt>
              <dd className="mt-0.5 tabular-nums">
                {formatPercent(result.baseline.churn_probability)}
              </dd>
            </div>
            <div>
              <dt className="text-ink-faint">Hypothetical probability</dt>
              <dd className="mt-0.5 tabular-nums">
                {formatPercent(selected.scenario_probability)}
              </dd>
            </div>
            <div>
              <dt className="text-ink-faint">Change</dt>
              <dd className="mt-0.5 tabular-nums">
                {formatPoints(selected.absolute_probability_change)}
              </dd>
            </div>
          </dl>
          <p className="mt-3 text-sm text-ink">{selected.model_based_interpretation}</p>
          <div className="mt-4">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
              Why the estimate moved
            </p>
            <ShapComparison deltas={selected.driver_deltas} />
          </div>
        </div>
      ) : null}

      {result.unsimulatable_interventions?.length ? (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
            Interventions the model cannot represent
          </p>
          <ul className="mt-2 space-y-1 text-sm text-ink-muted">
            {result.unsimulatable_interventions.map((item) => (
              <li key={item.strategy_id}>
                {item.intervention} — {item.reason}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
