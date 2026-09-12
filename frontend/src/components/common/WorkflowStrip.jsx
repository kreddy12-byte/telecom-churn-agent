const STEPS = ["Predict", "Explain", "Recommend", "Simulate", "Decide"];

export default function WorkflowStrip({ compact = false, current }) {
  const activeIndex = current
    ? STEPS.findIndex((step) => step.toLowerCase() === current.toLowerCase())
    : -1;

  return (
    <ol
      className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] uppercase tracking-[0.06em] ${
        compact ? "text-ink-muted" : "text-ink-faint"
      }`}
      aria-label="Decision workflow"
    >
      {STEPS.map((step, index) => (
        <li key={step} className="flex items-center gap-2">
          <span
            className={`font-semibold transition-colors duration-fast ${
              activeIndex === index
                ? "text-accent"
                : activeIndex > index
                  ? "text-ink-muted"
                  : "text-ink"
            }`}
          >
            {step}
          </span>
          {index < STEPS.length - 1 ? (
            <span aria-hidden="true" className="text-ink-faint/70">
              →
            </span>
          ) : null}
        </li>
      ))}
    </ol>
  );
}
