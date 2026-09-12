export const RISK_LEVELS = ["LOW", "MEDIUM", "HIGH"];

export function riskClasses(level) {
  switch (level) {
    case "HIGH":
      return "bg-risk-high-soft text-risk-high border-risk-high/35";
    case "MEDIUM":
      return "bg-risk-medium-soft text-risk-medium border-risk-medium/35";
    case "LOW":
      return "bg-risk-low-soft text-risk-low border-risk-low/35";
    default:
      return "bg-surface-muted text-ink-muted border-line";
  }
}

export function statusClasses(status) {
  switch (status) {
    case "APPROVED":
      return "bg-success-soft text-success border-success/35";
    case "REJECTED":
      return "bg-danger-soft text-danger border-danger/35";
    case "MODIFIED":
      return "bg-warning-soft text-warning border-warning/35";
    case "PENDING":
      return "bg-info-soft text-info border-info/35";
    default:
      return "bg-surface-muted text-ink-muted border-line";
  }
}

export function riskToneBorder(tone) {
  switch (tone) {
    case "high":
      return "border-l-risk-high";
    case "medium":
      return "border-l-risk-medium";
    case "low":
      return "border-l-risk-low";
    default:
      return "";
  }
}
