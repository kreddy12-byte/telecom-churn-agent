export const RISK_LEVELS = ["LOW", "MEDIUM", "HIGH"];

export function riskClasses(level) {
  switch (level) {
    case "HIGH":
      return "bg-rose-50 text-rose-800 border-rose-200";
    case "MEDIUM":
      return "bg-amber-50 text-amber-900 border-amber-200";
    case "LOW":
      return "bg-emerald-50 text-emerald-800 border-emerald-200";
    default:
      return "bg-slate-50 text-slate-700 border-slate-200";
  }
}

export function statusClasses(status) {
  switch (status) {
    case "APPROVED":
      return "bg-emerald-50 text-emerald-800 border-emerald-200";
    case "REJECTED":
      return "bg-rose-50 text-rose-800 border-rose-200";
    case "MODIFIED":
      return "bg-amber-50 text-amber-900 border-amber-200";
    case "PENDING":
      return "bg-sky-50 text-sky-900 border-sky-200";
    default:
      return "bg-slate-50 text-slate-700 border-slate-200";
  }
}
