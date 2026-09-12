const VARIANTS = {
  surface: "surface px-5 py-5",
  elevated: "surface-elevated px-5 py-5",
  ai: "ai-panel px-5 py-5 pl-6",
  shap: "shap-panel px-5 py-5",
  model: "model-panel px-5 py-5",
  decision: "decision-panel px-5 py-5",
};

const AI_VARIANTS = new Set(["ai", "shap"]);

export default function SectionCard({
  kicker,
  title,
  description,
  actions,
  children,
  className = "",
  elevated = false,
  variant,
}) {
  const shell =
    VARIANTS[variant] ||
    (elevated ? VARIANTS.elevated : VARIANTS.surface);
  const showAiBadge = AI_VARIANTS.has(variant);

  return (
    <section className={`${shell} ${className}`}>
      {(kicker || title || description || actions || showAiBadge) && (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              {kicker ? <p className="section-title">{kicker}</p> : null}
              {showAiBadge ? (
                <span className="inline-flex items-center rounded-control border border-ai-border bg-paper-raised/80 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.06em] text-accent">
                  AI
                </span>
              ) : null}
            </div>
            {title ? (
              <h2 className={`card-title ${kicker || showAiBadge ? "mt-1" : ""}`}>{title}</h2>
            ) : null}
            {description ? (
              <p className="mt-1.5 text-sm leading-6 text-ink-muted">{description}</p>
            ) : null}
          </div>
          {actions ? <div className="shrink-0">{actions}</div> : null}
        </div>
      )}
      {children}
    </section>
  );
}
