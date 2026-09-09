import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const COLORS = {
  Low: "#047857",
  Medium: "#b45309",
  High: "#be123c",
};

export default function RiskDistribution({ counts }) {
  const data = [
    { band: "Low", count: counts?.LOW ?? 0, key: "LOW" },
    { band: "Medium", count: counts?.MEDIUM ?? 0, key: "MEDIUM" },
    { band: "High", count: counts?.HIGH ?? 0, key: "HIGH" },
  ];
  const total = data.reduce((sum, row) => sum + row.count, 0);

  if (total === 0) {
    return (
      <p className="muted">
        No stored predictions yet. Risk distribution appears after customers
        are evaluated.
      </p>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_9rem]">
      <div className="h-36 min-w-0">
      <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 4, right: 12, top: 4, bottom: 0 }}>
            <XAxis type="number" allowDecimals={false} stroke="#8a93a0" fontSize={11} />
            <YAxis type="category" dataKey="band" width={64} stroke="#5a6573" fontSize={12} />
          <Tooltip
            cursor={{ fill: "#f3f4f6" }}
            formatter={(value) => [`${value} customers`, "Count"]}
          />
            <Bar dataKey="count" barSize={16} radius={[0, 2, 2, 0]}>
              {data.map((row) => (
                <Cell key={row.key} fill={COLORS[row.band]} />
              ))}
            </Bar>
        </BarChart>
      </ResponsiveContainer>
      </div>
      <ul className="space-y-2 text-sm">
        {data.map((row) => (
          <li key={row.key} className="flex items-baseline justify-between gap-3">
            <span className="text-ink-muted">
              {row.band}
              <span className="sr-only"> risk</span>
            </span>
            <span className="font-semibold tabular-nums text-ink">{row.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
