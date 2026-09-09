import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { formatCount, formatShare } from "../../utils/format";

// Same semantic colours as RiskBadge / the existing bar chart.
export const RISK_CHART_COLORS = {
  HIGH: "#be123c",
  MEDIUM: "#b45309",
  LOW: "#047857",
};

export function riskRows(counts, total) {
  return [
    { key: "HIGH", label: "HIGH RISK", count: counts?.HIGH ?? 0 },
    { key: "MEDIUM", label: "MEDIUM RISK", count: counts?.MEDIUM ?? 0 },
    { key: "LOW", label: "LOW RISK", count: counts?.LOW ?? 0 },
  ].map((row) => ({
    ...row,
    share: total > 0 ? row.count / total : 0,
    shareLabel: formatShare(row.count, total),
  }));
}

export function RiskDistributionChart({ counts, total }) {
  const data = riskRows(counts, total).filter((row) => row.count > 0);
  if (!data.length) {
    return <p className="muted">No scored customers to chart yet.</p>;
  }

  return (
    <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_11rem] sm:items-center">
      <div className="h-52 min-w-0" role="img" aria-label="Customer risk distribution donut chart">
        <ResponsiveContainer width="100%" height="100%" minWidth={120} minHeight={160}>
          <PieChart>
            <Pie
              data={data}
              dataKey="count"
              nameKey="label"
              innerRadius="58%"
              outerRadius="82%"
              paddingAngle={1.5}
              stroke="#ffffff"
              strokeWidth={1}
            >
              {data.map((row) => (
                <Cell key={row.key} fill={RISK_CHART_COLORS[row.key]} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value, name) => [`${formatCount(value)} customers`, name]}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="space-y-2 text-sm">
        {riskRows(counts, total).map((row) => (
          <li key={row.key} className="flex items-baseline justify-between gap-3">
            <span className="flex items-center gap-2 text-ink-muted">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ backgroundColor: RISK_CHART_COLORS[row.key] }}
                aria-hidden="true"
              />
              {row.label}
            </span>
            <span className="tabular-nums font-semibold text-ink">
              {formatCount(row.count)}
              <span className="ml-2 font-normal text-ink-muted">{row.shareLabel}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function RiskPriorityPanel({ counts, total }) {
  const rows = riskRows(counts, total);
  return (
    <div>
      <ul className="space-y-4">
        {rows.map((row) => (
          <li key={row.key}>
            <p className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
              {row.label}
            </p>
            <p className="mt-1 text-xl font-semibold tabular-nums tracking-tight">
              {formatCount(row.count)}{" "}
              <span className="text-sm font-normal text-ink-muted">customers</span>
            </p>
            <p className="text-sm text-ink-muted">{row.shareLabel} of scored customers</p>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full"
                style={{
                  width: `${Math.min(100, row.share * 100)}%`,
                  backgroundColor: RISK_CHART_COLORS[row.key],
                }}
              />
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-5 text-sm leading-6 text-ink-muted">
        High-risk customers are prioritized for deeper customer-level analysis and
        retention review. A HIGH band is a predicted probability, not a certainty
        that the customer will churn.
      </p>
    </div>
  );
}
