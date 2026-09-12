import { useEffect } from "react";

const TONES = {
  info: "border-info/35 bg-info-soft text-info",
  success: "border-success/35 bg-success-soft text-success",
  warning: "border-warning/35 bg-warning-soft text-warning",
  error: "border-danger/35 bg-danger-soft text-danger",
};

/**
 * Presentational toast surface. Parent owns visibility / queue.
 */
export default function Toast({ message, tone = "info", onDismiss, duration = 4000 }) {
  useEffect(() => {
    if (!onDismiss || !duration) return undefined;
    const id = window.setTimeout(onDismiss, duration);
    return () => window.clearTimeout(id);
  }, [onDismiss, duration]);

  if (!message) return null;

  return (
    <div
      role="status"
      className={`fixed bottom-5 right-5 z-50 max-w-sm animate-ri-fade-in rounded-panel border px-4 py-3 text-sm shadow-elevated ${TONES[tone] || TONES.info}`}
    >
      <div className="flex items-start gap-3">
        <p className="flex-1">{message}</p>
        {onDismiss ? (
          <button
            type="button"
            className="text-xs font-semibold opacity-80 hover:opacity-100"
            onClick={onDismiss}
          >
            Dismiss
          </button>
        ) : null}
      </div>
    </div>
  );
}
