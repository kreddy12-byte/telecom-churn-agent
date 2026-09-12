import Badge from "./Badge";
import { riskClasses } from "../../utils/risk";

/**
 * Compact risk signal for tables, KPIs, and charts.
 */
export default function RiskIndicator({ level, showLabel = true, className = "" }) {
  if (!level) {
    return <span className={`text-xs text-ink-faint ${className}`}>—</span>;
  }
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <span
        className={`h-2 w-2 rounded-full ${
          level === "HIGH"
            ? "bg-risk-high shadow-[0_0_8px_rgba(232,93,117,0.55)]"
            : level === "MEDIUM"
              ? "bg-risk-medium shadow-[0_0_8px_rgba(232,165,75,0.45)]"
              : "bg-risk-low shadow-[0_0_8px_rgba(61,186,140,0.45)]"
        }`}
        aria-hidden="true"
      />
      {showLabel ? (
        <Badge className={riskClasses(level)} tone="neutral">
          {level}
        </Badge>
      ) : (
        <span className="sr-only">{level} risk</span>
      )}
    </span>
  );
}
