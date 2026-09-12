import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CHART_THEME } from "../../design/tokens";
import { formatCount } from "../../utils/format";

export default function ProbabilityDistributionChart({ buckets }) {
  const data = buckets || [];
  const total = data.reduce((sum, row) => sum + Number(row.count || 0), 0);
  if (!total) {
    return <p className="muted">No probability histogram until customers are scored.</p>;
  }

  return (
    <div className="chart-shell h-56 min-w-0" role="img" aria-label="Churn probability distribution histogram">
      <ResponsiveContainer width="100%" height="100%" minWidth={160} minHeight={160}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
          <XAxis dataKey="bucket" tick={{ fontSize: 10, fill: CHART_THEME.axis }} interval={0} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: CHART_THEME.axis }} width={40} />
          <Tooltip
            contentStyle={{
              background: CHART_THEME.tooltipBg,
              border: `1px solid ${CHART_THEME.tooltipBorder}`,
              borderRadius: 8,
              color: CHART_THEME.tooltipText,
            }}
            formatter={(value) => [`${formatCount(value)} customers`, "Count"]}
            labelFormatter={(label) => `Predicted probability ${label}`}
          />
          <Bar dataKey="count" fill={CHART_THEME.accent} radius={[4, 4, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
