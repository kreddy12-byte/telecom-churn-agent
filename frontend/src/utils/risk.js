export const RISK_LEVELS = ["LOW", "MEDIUM", "HIGH"];

export function riskClasses(level) {
  switch (level) {
    case "HIGH":
      return "bg-risk-high-soft text-risk-high border-risk-high/25";
    case "MEDIUM":
      return "bg-risk-medium-soft text-risk-medium border-risk-medium/25";
    case "LOW":
      return "bg-risk-low-soft text-risk-low border-risk-low/25";
    default:
      return "bg-surface-muted text-ink-muted border-line";
  }
}

export function statusClasses(status) {
  switch (status) {
    case "APPROVED":
      return "bg-success-soft text-success border-success/25";
    case "REJECTED":
      return "bg-danger-soft text-danger border-danger/25";
    case "MODIFIED":
      return "bg-warning-soft text-warning border-warning/25";
    case "PENDING":
      return "bg-info-soft text-info border-info/25";
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

export function riskToneSurface(tone) {
  switch (tone) {
    case "high":
      return "bg-risk-high-soft";
    case "medium":
      return "bg-risk-medium-soft";
    case "low":
      return "bg-risk-low-soft";
    default:
      return "";
  }
}
