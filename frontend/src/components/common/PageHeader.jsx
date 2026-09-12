import Breadcrumb from "./Breadcrumb";

/**
 * Consistent page framing for shell routes.
 * Breadcrumbs are optional — prefer shell TopBar crumbs for global context,
 * and pass breadcrumbs here only when a page needs nested local context.
 */
export default function PageHeader({
  title,
  description,
  actions,
  eyebrow,
  breadcrumbs,
}) {
  return (
    <header className="mb-6">
      {breadcrumbs?.length ? <Breadcrumb items={breadcrumbs} /> : null}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          {eyebrow ? <p className="meta mb-1.5">{eyebrow}</p> : null}
          <h1 className="page-title">{title}</h1>
          {description ? <p className="page-subtitle">{description}</p> : null}
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
    </header>
  );
}
