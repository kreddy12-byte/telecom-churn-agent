const TONES = {
  high: "bg-risk-high",
  medium: "bg-risk-medium",
  low: "bg-risk-low",
  accent: "bg-accent",
  muted: "bg-ink-faint",
};

export default function ProgressBar({
  value = 0,
  max = 1,
  tone = "accent",
  className = "",
  label,
}) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <div
      className={`h-1.5 overflow-hidden rounded-full bg-surface-interactive ${className}`}
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <div
        className={`h-full rounded-full transition-[width] duration-ri ease-ri ${TONES[tone] || TONES.accent}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
