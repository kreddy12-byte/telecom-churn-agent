import RiskBadge from "../common/RiskBadge";
import { featureLabel, strategyLabel } from "../../utils/format";

const FALLBACK_PROVIDER = "deterministic_fallback";

function evidenceDirection(item) {
  return item.direction === "increases_risk"
    ? "increases churn risk"
    : "decreases churn risk";
}

export default function RecommendationPanel({ recommendation, loading, error }) {
  if (loading) {
    return (
      <p className="muted" role="status">
        Loading retention recommendation…
      </p>
    );
  }
  if (error) {
    return <p className="text-sm text-rose-800">{error}</p>;
  }
  if (!recommendation) {
    return <p className="muted">No retention recommendation is available yet.</p>;
  }

  const strategy =
    recommendation.selected_strategy?.strategy_name ||
    strategyLabel(recommendation.selected_strategy?.strategy_id);
  const reasons = recommendation.reasoning?.length
    ? recommendation.reasoning
    : recommendation.reason
      ? [recommendation.reason]
      : [];
  const evidence = recommendation.supporting_evidence || [];
  const priority = recommendation.priority || recommendation.risk_level;
  const isFallback = recommendation.provider === FALLBACK_PROVIDER;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-panel border border-line bg-slate-50 px-2 py-0.5 text-[11px] font-semibold tracking-wide text-ink">
          Recommended retention action
        </span>
        <span className="rounded-panel border border-amber-300 bg-amber-50 px-2 py-0.5 text-[11px] font-semibold tracking-wide text-amber-900">
          Human approval required
        </span>
        {isFallback ? (
          <span className="rounded-panel border border-line bg-white px-2 py-0.5 text-[11px] font-semibold tracking-wide text-ink-muted">
            System-generated fallback reasoning
          </span>
        ) : null}
      </div>

      <dl className="grid gap-4 sm:grid-cols-3">
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
            Recommended action
          </dt>
          <dd className="mt-1 text-sm font-semibold text-ink">{strategy || "—"}</dd>
        </div>
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
            Confidence
          </dt>
          <dd className="mt-1 text-sm font-semibold text-ink">
            {recommendation.confidence || "—"}
          </dd>
        </div>
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
            Priority
          </dt>
          <dd className="mt-1">
            {priority ? (
              <RiskBadge level={priority} noun="priority" />
            ) : (
              <span className="text-sm text-ink-faint">—</span>
            )}
          </dd>
        </div>
      </dl>

      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
          Recommendation
        </p>
        <p className="mt-1 text-sm leading-6 text-ink">{recommendation.recommendation}</p>
      </div>

      {reasons.length ? (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
            Why this action was selected
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-ink">
            {reasons.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {isFallback && recommendation.fallback_reason ? (
        <p className="text-sm text-ink-muted">{recommendation.fallback_reason}</p>
      ) : null}

      {evidence.length ? (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
            Supporting evidence
          </p>
          <ul className="mt-2 space-y-1 text-sm text-ink-muted">
            {evidence.map((item) => (
              <li key={`${item.feature}-${item.value}`}>
                {featureLabel(item.feature)}
                {item.value != null ? ` = ${item.value}` : ""} · {evidenceDirection(item)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {recommendation.objective ? (
        <p className="text-sm text-ink-muted">
          <span className="font-medium text-ink">Objective. </span>
          {recommendation.objective}
        </p>
      ) : null}
    </div>
  );
}
