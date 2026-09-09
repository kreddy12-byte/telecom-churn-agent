import { featureLabel, formatShap } from "../../utils/format";

export default function ShapBars({ drivers }) {
  const rows = drivers || [];
  if (!rows.length) {
    return <p className="muted">No churn drivers are available for this prediction.</p>;
  }

  const maxAbs = Math.max(
    0.0001,
    ...rows.map((driver) => Math.abs(Number(driver.shap_value) || 0))
  );

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-4 text-xs text-ink-muted">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-3 bg-rose-600" aria-hidden="true" />
          Increases churn risk
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-3 bg-emerald-700" aria-hidden="true" />
          Decreases churn risk
        </span>
      </div>
      <div className="space-y-3">
        {rows.map((driver) => {
          const value = Number(driver.shap_value) || 0;
          const width = `${(Math.abs(value) / maxAbs) * 50}%`;
          const increases = driver.direction === "increases_risk";
          return (
            <div key={driver.feature}>
              <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
                <div>
                  <span className="font-medium text-ink">{featureLabel(driver.feature)}</span>
                  {driver.value != null ? (
                    <span className="ml-2 text-ink-muted">{String(driver.value)}</span>
                  ) : null}
                </div>
                <div className="tabular-nums text-ink">
                  {formatShap(value)}
                  <span className="ml-2 text-xs text-ink-muted">
                    {increases ? "Increases churn risk" : "Decreases churn risk"}
                  </span>
                </div>
              </div>
              <div className="relative h-2 bg-slate-100">
                <div className="absolute inset-y-0 left-1/2 w-px bg-slate-300" aria-hidden="true" />
                <div
                  className={`absolute top-0 h-2 ${increases ? "left-1/2 bg-rose-600" : "right-1/2 bg-emerald-700"}`}
                  style={{ width }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-4 text-xs leading-5 text-ink-muted">
        SHAP explains how features influenced this model prediction; it does not
        prove that a feature causes churn.
      </p>
    </div>
  );
}
