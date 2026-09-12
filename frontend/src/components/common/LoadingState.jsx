export default function LoadingState({ label = "Loading…", className = "" }) {
  return (
    <div
      className={`flex items-center justify-center gap-3 py-10 text-sm text-ink-muted ${className}`}
      role="status"
      aria-live="polite"
    >
      <span
        className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-accent"
        aria-hidden="true"
      />
      <span>{label}</span>
    </div>
  );
}
