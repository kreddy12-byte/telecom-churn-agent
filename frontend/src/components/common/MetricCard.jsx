export default function MetricCard({ label, value, hint, tone }) {
  const toneClass =
    tone === "high"
      ? "border-l-2 border-l-rose-700"
      : tone === "medium"
        ? "border-l-2 border-l-amber-600"
        : tone === "low"
          ? "border-l-2 border-l-emerald-700"
          : "";
  return (
    <div className={`surface px-4 py-3.5 ${toneClass}`}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
        {label}
      </p>
      <p className="mt-1.5 text-[1.65rem] font-semibold tabular-nums leading-none tracking-tight">
        {value}
      </p>
      {hint ? <p className="mt-1.5 text-xs text-ink-muted">{hint}</p> : null}
    </div>
  );
}
