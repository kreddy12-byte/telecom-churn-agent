export default function ErrorBanner({ message, onRetry }) {
  return (
    <div
      role="alert"
      className="rounded-panel border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p>{message || "Unable to load this view."}</p>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="rounded-panel border border-rose-300 bg-white px-3 py-1 text-xs font-semibold text-rose-900 hover:bg-rose-50"
          >
            Try again
          </button>
        ) : null}
      </div>
    </div>
  );
}
