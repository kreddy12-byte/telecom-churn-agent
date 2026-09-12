import { Link } from "react-router-dom";

export default function Breadcrumb({ items = [], className = "mb-3" }) {
  if (!items.length) return null;
  return (
    <nav aria-label="Breadcrumb" className={className}>
      <ol className="flex flex-wrap items-center gap-1.5 text-xs text-ink-faint">
        {items.map((item, index) => {
          const last = index === items.length - 1;
          return (
            <li key={`${item.label}-${index}`} className="flex items-center gap-1.5">
              {index > 0 ? (
                <span aria-hidden="true" className="text-ink-faint/50">
                  /
                </span>
              ) : null}
              {last || !item.to ? (
                <span
                  className={last ? "font-medium text-ink-muted" : ""}
                  aria-current={last ? "page" : undefined}
                >
                  {item.label}
                </span>
              ) : (
                <Link
                  to={item.to}
                  className="transition-colors duration-fast hover:text-ink"
                >
                  {item.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
