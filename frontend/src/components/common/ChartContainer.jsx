export default function ChartContainer({
  title,
  description,
  actions,
  children,
  className = "",
  heightClass = "h-52",
}) {
  return (
    <div className={`chart-shell ${className}`}>
      {(title || description || actions) && (
        <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
          <div>
            {title ? <h3 className="card-title">{title}</h3> : null}
            {description ? <p className="mt-0.5 text-xs text-ink-muted">{description}</p> : null}
          </div>
          {actions ? <div>{actions}</div> : null}
        </div>
      )}
      <div className={`min-w-0 ${heightClass}`}>{children}</div>
    </div>
  );
}
