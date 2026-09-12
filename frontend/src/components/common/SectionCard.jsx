const VARIANTS = {
  surface: "surface px-5 py-4",
  elevated: "surface-elevated px-5 py-4",
  ai: "ai-panel px-5 py-4 pl-6",
  shap: "shap-panel px-5 py-4",
  model: "model-panel px-5 py-4",
  decision: "decision-panel px-5 py-4",
};

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

  return (
    <section className={`${shell} ${className}`}>
      {(kicker || title || description || actions) && (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            {kicker ? <p className="section-title">{kicker}</p> : null}
            {title ? (
              <h2 className={`card-title ${kicker ? "mt-1" : ""}`}>{title}</h2>
            ) : null}
            {description ? (
              <p className="mt-1 text-sm leading-6 text-ink-muted">{description}</p>
            ) : null}
          </div>
          {actions ? <div className="shrink-0">{actions}</div> : null}
        </div>
      )}
      {children}
    </section>
  );
}
