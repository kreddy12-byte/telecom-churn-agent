import { statusClasses } from "../../utils/risk";

export default function StatusBadge({ status }) {
  if (!status) {
    return <span className="text-sm text-ink-faint">No action</span>;
  }
  return (
    <span
      className={`inline-flex items-center rounded-panel border px-2 py-0.5 text-[11px] font-semibold tracking-wide ${statusClasses(status)}`}
    >
      {status}
    </span>
  );
}
