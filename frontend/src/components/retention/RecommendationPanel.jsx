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
    return <p className="text-sm text-danger">{error}</p>;
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
        <span className="rounded-control border border-ai-border bg-ai-soft px-2 py-0.5 text-[11px] font-semibold tracking-wide text-accent">
          Recommended retention action
        </span>
        <span className="rounded-control border border-warning/35 bg-warning-soft px-2 py-0.5 text-[11px] font-semibold tracking-wide text-warning">
          Human approval required
        </span>
        {isFallback ? (
          <span className="rounded-control border border-line bg-surface-muted px-2 py-0.5 text-[11px] font-semibold tracking-wide text-ink-muted">
            System-generated fallback reasoning
          </span>
        ) : null}
      </div>

      <dl className="grid gap-4 sm:grid-cols-3">
        <div>
          <dt className="meta">Recommended action</dt>
          <dd className="mt-1 text-sm font-semibold text-ink">{strategy || "—"}</dd>
        </div>
        <div>
          <dt className="meta">Confidence</dt>
          <dd className="mt-1 text-sm font-semibold text-ink">
            {recommendation.confidence || "—"}
          </dd>
        </div>
        <div>
          <dt className="meta">Priority</dt>
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
        <p className="meta">Recommendation</p>
        <p className="mt-1 text-sm leading-6 text-ink">{recommendation.recommendation}</p>
      </div>

      {reasons.length ? (
        <div>
          <p className="meta">Why this action was selected</p>
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
