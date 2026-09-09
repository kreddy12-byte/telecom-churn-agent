import { featureLabel, formatShap } from "../../utils/format";

export default function ShapComparison({ deltas }) {
  if (!deltas?.length) {
    return <p className="muted">No SHAP comparison is available for this scenario.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="data-table">
        <thead>
          <tr>
            <th>Churn driver</th>
            <th className="text-right">Baseline</th>
            <th className="text-right">Scenario</th>
            <th className="text-right">Moved</th>
          </tr>
        </thead>
        <tbody>
          {deltas.slice(0, 8).map((delta) => (
            <tr key={delta.feature}>
              <td>
                {featureLabel(delta.feature)}
                {delta.changed_by_scenario ? (
                  <span className="ml-2 text-xs text-ink-faint">changed</span>
                ) : null}
              </td>
              <td className="text-right tabular-nums">{formatShap(delta.baseline_shap)}</td>
              <td className="text-right tabular-nums">{formatShap(delta.scenario_shap)}</td>
              <td className="text-right tabular-nums">{formatShap(delta.shap_change)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
