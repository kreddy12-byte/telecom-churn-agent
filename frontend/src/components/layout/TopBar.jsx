import UserMenu from "./UserMenu";

export default function TopBar({ health, modelVersion, user, role, onSignOut }) {
  const status =
    health == null
      ? { label: "Loading", tone: "bg-slate-400", text: "Checking API" }
      : health.status === "healthy"
        ? { label: "Connected", tone: "bg-emerald-600", text: "API connected" }
        : health.status === "degraded"
          ? { label: "Degraded", tone: "bg-amber-500", text: "API degraded" }
          : { label: "Unavailable", tone: "bg-rose-600", text: "API unavailable" };

  return (
    <header className="flex items-center justify-between gap-4 border-b border-line bg-white px-5 py-2.5">
      <div className="min-w-0">
        <p className="truncate text-sm text-ink-muted">
          ML predicts · SHAP explains · AI recommends · What-if evaluates · Human approves
        </p>
      </div>
      <div className="flex flex-wrap items-center justify-end gap-3 text-xs text-ink-muted">
        <span
          className="inline-flex items-center gap-1.5"
          aria-live="polite"
          aria-label={`API status: ${status.label}`}
        >
          <span className={`h-2 w-2 rounded-full ${status.tone}`} aria-hidden="true" />
          <span>
            <span className="font-semibold text-ink">{status.label}</span>
            <span className="sr-only"> — {status.text}</span>
          </span>
        </span>
        {modelVersion ? <span>Model {modelVersion}</span> : null}
        {user ? <UserMenu user={user} role={role} onSignOut={onSignOut} /> : null}
      </div>
    </header>
  );
}
