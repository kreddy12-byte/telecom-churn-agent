import { featureLabel } from "../../utils/format";

export default function ChurnDriversChart({ drivers }) {
  const rows = drivers || [];
  if (!rows.length) {
    return <p className="muted">Global driver ranking is not available.</p>;
  }
  const maxAbs = Math.max(
    0.0001,
    ...rows.map((row) => Number(row.mean_absolute_shap) || 0)
  );

  return (
    <div>
      <ul className="space-y-3">
        {rows.map((row) => {
          const magnitude = Number(row.mean_absolute_shap) || 0;
          const width = `${(magnitude / maxAbs) * 100}%`;
          return (
            <li key={row.feature}>
              <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
                <span className="font-medium text-ink">{featureLabel(row.feature)}</span>
                <span className="tabular-nums text-ink-muted">
                  {magnitude.toFixed(3)}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full bg-accent"
                  style={{ width }}
                  title={`${featureLabel(row.feature)} mean |SHAP| ${magnitude.toFixed(3)}`}
                />
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-4 text-xs leading-5 text-ink-muted">
        Global drivers summarize patterns in the model; they do not imply causation.
      </p>
    </div>
  );
}
