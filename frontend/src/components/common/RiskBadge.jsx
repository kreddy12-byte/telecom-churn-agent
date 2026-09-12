import { riskClasses } from "../../utils/risk";

const MARK = {
  HIGH: { symbol: "▲", label: "High" },
  MEDIUM: { symbol: "■", label: "Medium" },
  LOW: { symbol: "●", label: "Low" },
};

export default function RiskBadge({ level, noun = "risk", className = "" }) {
  if (!level) {
    return <span className="text-sm text-ink-faint">Not evaluated</span>;
  }
  const mark = MARK[level] || { symbol: "○", label: level };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-control border px-2 py-0.5 text-[11px] font-semibold tracking-wide transition-colors duration-fast ease-ri ${riskClasses(level)} ${className}`}
    >
      <span aria-hidden="true" className="text-[9px] opacity-90">
        {mark.symbol}
      </span>
      <span>
        {level} {noun}
        <span className="sr-only"> ({mark.label})</span>
      </span>
    </span>
  );
}
