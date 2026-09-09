export default function SectionCard({
  kicker,
  title,
  description,
  actions,
  children,
  className = "",
}) {
  return (
    <section className={`surface px-5 py-4 ${className}`}>
      {(kicker || title || description || actions) && (
        <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
          <div>
            {kicker ? (
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-faint">
                {kicker}
              </p>
            ) : null}
            {title ? (
              <h2 className={`text-sm font-semibold text-ink ${kicker ? "mt-1" : ""}`}>
                {title}
              </h2>
            ) : null}
            {description ? <p className="mt-1 text-sm text-ink-muted">{description}</p> : null}
          </div>
          {actions ? <div className="shrink-0">{actions}</div> : null}
        </div>
      )}
      {children}
    </section>
  );
}
