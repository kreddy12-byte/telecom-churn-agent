import { riskToneBorder, riskToneSurface } from "../../utils/risk";

const TONE_MARK = {
  high: { label: "High risk", className: "text-risk-high bg-paper-raised/80" },
  medium: { label: "Medium risk", className: "text-risk-medium bg-paper-raised/80" },
  low: { label: "Low risk", className: "text-risk-low bg-paper-raised/80" },
};

function ToneIcon({ tone }) {
  const mark = TONE_MARK[tone];
  if (!mark) return null;
  return (
    <span
      className={`inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-control ${mark.className}`}
      aria-hidden="true"
      title={mark.label}
    >
      {tone === "high" ? (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 4l9 16H3L12 4z" />
        </svg>
      ) : tone === "medium" ? (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <rect x="5" y="5" width="14" height="14" rx="2" />
        </svg>
      ) : (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <circle cx="12" cy="12" r="7" />
        </svg>
      )}
    </span>
  );
}

export default function MetricCard({ label, value, hint, tone }) {
  const toneBorder = tone ? `border-l-[3px] ${riskToneBorder(tone)}` : "";
  const toneSurface = tone ? riskToneSurface(tone) : "";

  return (
    <div className={`surface px-4 py-4 ${toneBorder} ${toneSurface}`}>
      <div className="flex items-start justify-between gap-3">
        <p className="meta">{label}</p>
        <ToneIcon tone={tone} />
      </div>
      <p className="kpi-value mt-2.5">{value}</p>
      {hint ? <p className="mt-2 text-xs leading-5 text-ink-muted">{hint}</p> : null}
    </div>
  );
}

/** Alias for the design-system KPI name. */
export function KPI(props) {
  return <MetricCard {...props} />;
}
