import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../components/common/PageHeader";
import ErrorBanner from "../components/common/ErrorBanner";
import EmptyState from "../components/common/EmptyState";
import { TableSkeleton } from "../components/common/Skeleton";
import StatusBadge from "../components/common/StatusBadge";
import Button from "../components/common/Button";
import { formatDate, formatPageRange, strategyLabel } from "../utils/format";
import { apiErrorMessage, getActions } from "../services/api";

const FILTERS = ["", "PENDING", "APPROVED", "MODIFIED", "REJECTED"];
const PAGE_SIZE = 20;

export default function Actions() {
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  function load() {
    setError(null);
    getActions({ status: status || undefined, limit: PAGE_SIZE, offset })
      .then(setData)
      .catch((err) => setError(apiErrorMessage(err)));
  }

  useEffect(() => {
    load();
  }, [status, offset]);

  const total = data?.meta?.total ?? 0;

  return (
    <div>
      <PageHeader
        title="Retention actions"
        description="Decisions recorded from Customer Intelligence. Approving a row does not contact a customer."
      />

      <div className="mb-4 flex flex-wrap gap-2">
        {FILTERS.map((value) => (
          <Button
            key={value || "all"}
            variant={status === value ? "primary" : "secondary"}
            onClick={() => {
              setStatus(value);
              setOffset(0);
            }}
          >
            {value || "All"}
          </Button>
        ))}
      </div>

      {error ? <ErrorBanner message={error} onRetry={load} /> : null}
      {!data && !error ? <TableSkeleton /> : null}
      {data && data.items.length === 0 ? (
        <EmptyState
          title="No review actions in this filter"
          body="Open a customer intelligence page to record a decision."
        />
      ) : null}

      {data && data.items.length > 0 ? (
        <div className="surface overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Customer</th>
                <th>Strategy</th>
                <th>Decision</th>
                <th>Reviewer</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.id}>
                  <td className="whitespace-nowrap font-medium">
                    <Link
                      to={`/customers/${row.customer_id}`}
                      className="text-accent hover:underline"
                    >
                      {row.customer_id}
                    </Link>
                  </td>
                  <td className="max-w-sm text-ink-muted">
                    <p className="font-medium text-ink">{strategyLabel(row.strategy_id)}</p>
                    <p className="mt-0.5 line-clamp-2">{row.recommendation}</p>
                  </td>
                  <td>
                    <StatusBadge status={row.status} />
                  </td>
                  <td className="max-w-xs text-ink-muted">
                    <p>{row.reviewed_by_name || "—"}</p>
                    <p className="text-xs">{row.reviewed_by_email || "—"}</p>
                    {row.reviewer_note ? (
                      <p className="mt-1 text-xs">{row.reviewer_note}</p>
                    ) : null}
                  </td>
                  <td className="whitespace-nowrap text-ink-muted">
                    <p>{formatDate(row.updated_at)}</p>
                    <p className="text-xs">Created {formatDate(row.created_at)}</p>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {data ? (
        <div className="mt-4 flex justify-between text-sm text-ink-muted">
          <p>{formatPageRange(total, offset, PAGE_SIZE)}</p>
          <div className="flex gap-2">
            <Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
              Previous
            </Button>
            <Button
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Next
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
