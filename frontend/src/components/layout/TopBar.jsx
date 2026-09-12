import { useLocation } from "react-router-dom";
import Breadcrumb from "../common/Breadcrumb";
import IconButton from "../common/IconButton";
import { breadcrumbsForPath } from "./navigation";

export default function TopBar({
  health,
  modelVersion,
  onOpenNav,
  navOpen = false,
  navPanelId,
}) {
  const { pathname } = useLocation();
  const crumbs = breadcrumbsForPath(pathname);

  const status =
    health == null
      ? { label: "Checking", tone: "bg-ink-faint", text: "Checking API" }
      : health.status === "healthy"
        ? { label: "Online", tone: "bg-success", text: "API connected" }
        : health.status === "degraded"
          ? { label: "Degraded", tone: "bg-warning", text: "API degraded" }
          : { label: "Offline", tone: "bg-danger", text: "API unavailable" };

  return (
    <header className="sticky top-0 z-20 border-b border-line bg-paper-raised/95 backdrop-blur-md">
      <div className="flex items-center justify-between gap-3 px-4 py-3 sm:px-5 lg:px-6">
        <div className="flex min-w-0 items-center gap-2.5">
          {onOpenNav ? (
            <IconButton
              label={navOpen ? "Close navigation" : "Open navigation"}
              className="lg:hidden"
              onClick={onOpenNav}
              aria-expanded={navOpen}
              aria-controls={navPanelId}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                {navOpen ? (
                  <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
                ) : (
                  <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
                )}
              </svg>
            </IconButton>
          ) : null}

          <div className="min-w-0">
            {crumbs.length ? (
              <Breadcrumb items={crumbs} className="mb-0" />
            ) : (
              <p className="truncate text-xs text-ink-faint">Churn Intelligence</p>
            )}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2 text-xs text-ink-muted">
          {modelVersion ? (
            <span
              className="hidden rounded-control border border-line bg-surface-muted px-2 py-1 font-mono text-[10px] tracking-tight text-ink-muted sm:inline-flex"
              title="Active model version"
            >
              {modelVersion}
            </span>
          ) : null}

          <span
            className="inline-flex items-center gap-1.5 rounded-control border border-line bg-surface-muted px-2 py-1"
            aria-live="polite"
            aria-label={`API status: ${status.label}`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${status.tone}`} aria-hidden="true" />
            <span className="font-medium text-ink">{status.label}</span>
            <span className="sr-only"> — {status.text}</span>
          </span>
        </div>
      </div>
    </header>
  );
}
