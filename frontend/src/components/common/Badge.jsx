const TONES = {
  neutral: "bg-surface-muted text-ink-muted border-line",
  accent: "bg-accent-soft text-accent border-accent/30",
  info: "bg-info-soft text-info border-info/30",
  success: "bg-success-soft text-success border-success/30",
  warning: "bg-warning-soft text-warning border-warning/30",
  danger: "bg-danger-soft text-danger border-danger/30",
  ai: "bg-ai-soft text-accent border-ai-border",
};

export default function Badge({ children, tone = "neutral", className = "" }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-control border px-2 py-0.5 text-[11px] font-semibold tracking-wide ${TONES[tone] || TONES.neutral} ${className}`}
    >
      {children}
    </span>
  );
}
