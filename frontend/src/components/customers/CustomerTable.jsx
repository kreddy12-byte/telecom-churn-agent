import { Link } from "react-router-dom";
import RiskBadge from "../common/RiskBadge";
import StatusBadge from "../common/StatusBadge";
import { formatDate, formatMoney, formatPercent } from "../../utils/format";

export default function CustomerTable({ items }) {
  return (
    <div className="surface overflow-x-auto">
      <table className="data-table">
        <thead>
          <tr>
            <th>Customer</th>
            <th>Contract</th>
            <th className="text-right">Tenure</th>
            <th className="text-right">Monthly charges</th>
            <th className="text-right">Churn probability</th>
            <th>Risk</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => {
            const prediction = row.latest_prediction;
            return (
              <tr key={row.customer_id}>
                <td className="font-semibold">
                  <Link
                    to={`/customers/${row.customer_id}`}
                    className="text-accent hover:underline"
                  >
                    {row.customer_id}
                  </Link>
                </td>
                <td className="text-ink-muted">{row.contract ?? "—"}</td>
                <td className="text-right tabular-nums text-ink-muted">
                  {row.tenure != null ? `${row.tenure} mo` : "—"}
                </td>
                <td className="text-right tabular-nums text-ink-muted">
                  {formatMoney(row.monthly_charges)}
                </td>
                <td className="text-right tabular-nums font-semibold text-ink">
                  {prediction ? formatPercent(prediction.churn_probability) : "—"}
                </td>
                <td>
                  <RiskBadge level={prediction?.risk_level} />
                </td>
                <td>
                  <Link
                    to={`/customers/${row.customer_id}`}
                    className="text-sm font-medium text-accent hover:underline"
                  >
                    View intelligence
                    <span className="sr-only"> for {row.customer_id}</span>
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function PriorityRankingTable({ items }) {
  return (
    <div className="overflow-x-auto">
      <table className="data-table">
        <thead>
          <tr>
            <th>Customer</th>
            <th className="text-right">Churn probability</th>
            <th>Risk</th>
            <th>Contract</th>
            <th className="text-right">Tenure</th>
            <th className="text-right">Monthly charges</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.customer_id}>
              <td className="font-semibold">
                <Link
                  to={`/customers/${row.customer_id}`}
                  className="text-accent hover:underline"
                >
                  {row.customer_id}
                </Link>
              </td>
              <td className="text-right tabular-nums font-semibold text-ink">
                {formatPercent(row.churn_probability)}
              </td>
              <td>
                <RiskBadge level={row.risk_level} />
              </td>
              <td className="text-ink-muted">{row.contract ?? "—"}</td>
              <td className="text-right tabular-nums text-ink-muted">
                {row.tenure != null ? `${row.tenure} mo` : "—"}
              </td>
              <td className="text-right tabular-nums text-ink-muted">
                {formatMoney(row.monthly_charges)}
              </td>
              <td>
                <Link
                  to={`/customers/${row.customer_id}`}
                  className="inline-flex items-center rounded-control border border-accent/25 bg-accent-soft px-2.5 py-1 text-xs font-semibold text-accent transition-colors hover:bg-accent hover:text-ink-inverse"
                >
                  View intelligence
                  <span className="sr-only"> for {row.customer_id}</span>
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function HighRiskTable({ items }) {
  return (
    <div className="overflow-x-auto">
      <table className="data-table">
        <thead>
          <tr>
            <th>Customer</th>
            <th>Risk</th>
            <th className="text-right">Churn probability</th>
            <th>Last evaluated</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.customer_id}>
              <td className="font-semibold">
                <Link
                  to={`/customers/${row.customer_id}`}
                  className="text-accent hover:underline"
                >
                  {row.customer_id}
                </Link>
              </td>
              <td>
                <RiskBadge level={row.latest_prediction?.risk_level} />
              </td>
              <td className="text-right tabular-nums font-semibold">
                {formatPercent(row.latest_prediction?.churn_probability)}
              </td>
              <td className="text-ink-muted">
                {formatDate(row.latest_prediction?.created_at)}
              </td>
              <td>
                <StatusBadge status={row.latest_action?.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
