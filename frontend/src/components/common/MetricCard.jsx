import { riskToneBorder } from "../../utils/risk";

export default function MetricCard({ label, value, hint, tone }) {
  const toneClass = tone ? `border-l-2 ${riskToneBorder(tone)}` : "";
  return (
    <div className={`surface px-4 py-3.5 ${toneClass}`}>
      <p className="meta">{label}</p>
      <p className="kpi-value mt-2">{value}</p>
      {hint ? <p className="mt-2 text-xs text-ink-muted">{hint}</p> : null}
    </div>
  );
}

/** Alias for the design-system KPI name. */
export function KPI(props) {
  return <MetricCard {...props} />;
}
