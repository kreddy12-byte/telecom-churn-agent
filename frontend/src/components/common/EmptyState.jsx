import Button from "./Button";

export default function EmptyState({ title, body, actionLabel, onAction, className = "" }) {
  return (
    <div className={`surface px-6 py-10 text-center ${className}`}>
      <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-full border border-line bg-surface-muted text-accent">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
          <rect x="3" y="4" width="18" height="16" rx="2" />
          <path d="M7 9h10M7 13h6" strokeLinecap="round" />
        </svg>
      </div>
      <p className="text-sm font-semibold text-ink">{title}</p>
      {body ? <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-ink-muted">{body}</p> : null}
      {actionLabel && onAction ? (
        <div className="mt-5">
          <Button variant="primary" onClick={onAction}>
            {actionLabel}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
