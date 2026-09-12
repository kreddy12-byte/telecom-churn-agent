import Button from "./Button";

const TONES = {
  error: "border-danger/35 bg-danger-soft text-danger",
  warning: "border-warning/35 bg-warning-soft text-warning",
  info: "border-info/35 bg-info-soft text-info",
  success: "border-success/35 bg-success-soft text-success",
};

export function Alert({
  tone = "error",
  title,
  children,
  onRetry,
  retryLabel = "Try again",
  className = "",
}) {
  return (
    <div role="alert" className={`rounded-panel border px-4 py-3 text-sm ${TONES[tone] || TONES.error} ${className}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          {title ? <p className="font-semibold">{title}</p> : null}
          {children ? <div className={title ? "mt-1 opacity-90" : ""}>{children}</div> : null}
        </div>
        {onRetry ? (
          <Button
            variant="secondary"
            size="sm"
            onClick={onRetry}
            className="shrink-0 border-current/30 bg-transparent hover:bg-paper-raised/5"
          >
            {retryLabel}
          </Button>
        ) : null}
      </div>
    </div>
  );
}

export default Alert;
