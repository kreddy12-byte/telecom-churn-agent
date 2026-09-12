import { statusClasses } from "../../utils/risk";

export default function StatusBadge({ status }) {
  if (!status) {
    return <span className="text-sm text-ink-faint">No action</span>;
  }
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-control border px-2 py-0.5 text-[11px] font-semibold tracking-wide ${statusClasses(status)}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-80" aria-hidden="true" />
      {status}
    </span>
  );
}
