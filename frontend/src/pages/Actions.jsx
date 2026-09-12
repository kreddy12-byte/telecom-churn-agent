import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../components/common/PageHeader";
import ErrorBanner from "../components/common/ErrorBanner";
import EmptyState from "../components/common/EmptyState";
import { TableSkeleton, KpiSkeleton } from "../components/common/Skeleton";
import StatusBadge from "../components/common/StatusBadge";
import MetricCard from "../components/common/MetricCard";
import Button from "../components/common/Button";
import Badge from "../components/common/Badge";
import { formatCount, formatDate, formatPageRange, strategyLabel } from "../utils/format";
import { apiErrorMessage, getActions, getOverview } from "../services/api";

const FILTERS = ["", "PENDING", "APPROVED", "MODIFIED", "REJECTED"];
const PAGE_SIZE = 20;

export default function Actions() {
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState(null);
  const [overview, setOverview] = useState(null);
  const [error, setError] = useState(null);

  function load() {
    setError(null);
    return getActions({ status: status || undefined, limit: PAGE_SIZE, offset })
      .then(setData)
      .catch((err) => setError(apiErrorMessage(err)));
  }

  useEffect(() => {
    let cancelled = false;
    setError(null);
    getActions({ status: status || undefined, limit: PAGE_SIZE, offset })
      .then((next) => {
        if (!cancelled) setData(next);
      })
      .catch((err) => {
        if (!cancelled) setError(apiErrorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [status, offset]);

  useEffect(() => {
    let cancelled = false;
    getOverview()
      .then((next) => {
        if (!cancelled) setOverview(next);
      })
      .catch(() => {
        if (!cancelled) setOverview(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const total = data?.meta?.total ?? 0;
  const actionCounts = overview?.action_counts;
  const pending = actionCounts?.PENDING ?? null;
  const approved = actionCounts?.APPROVED ?? null;
  const modified = actionCounts?.MODIFIED ?? null;
  const rejected = actionCounts?.REJECTED ?? null;
  const recorded =
    pending != null && approved != null && modified != null && rejected != null
      ? pending + approved + modified + rejected
      : null;

  const filterLabel = useMemo(
    () => (status ? status : "All recorded decisions"),
    [status]
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title="Retention Actions"
        description="Prioritize customers and act on the strongest available retention opportunities."
      />

      {actionCounts ? (
        <section aria-label="Action summary" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Recorded decisions"
            value={formatCount(recorded)}
            hint="All retention reviews stored for reviewers."
          />
          <MetricCard
            label="Pending"
            value={formatCount(pending)}
            hint="Awaiting human approval."
            tone="medium"
          />
          <MetricCard
            label="Approved"
            value={formatCount(approved)}
            hint="Accepted recommendations."
            tone="low"
          />
          <MetricCard
            label="Rejected / modified"
            value={formatCount((rejected || 0) + (modified || 0))}
            hint="Rejected or changed by a reviewer."
          />
        </section>
      ) : !error && !data ? (
        <KpiSkeleton count={4} />
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <span className="meta mr-1">Status</span>
        {FILTERS.map((value) => (
          <Button
            key={value || "all"}
            size="sm"
            variant={status === value ? "primary" : "secondary"}
            onClick={() => {
              setStatus(value);
              setOffset(0);
            }}
          >
            {value || "All"}
          </Button>
        ))}
        <Badge tone="neutral" className="ml-auto">
          {filterLabel}
        </Badge>
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
                <th>Recommended action</th>
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
                  <td className="max-w-sm">
                    <p className="font-medium text-ink">{strategyLabel(row.strategy_id)}</p>
                    <p className="mt-0.5 line-clamp-2 text-ink-muted">{row.recommendation}</p>
                  </td>
                  <td>
                    <StatusBadge status={row.status} />
                  </td>
                  <td className="max-w-xs text-ink-muted">
                    <p className="text-ink">{row.reviewed_by_name || "—"}</p>
                    <p className="text-xs">{row.reviewed_by_email || "—"}</p>
                    {row.reviewer_note ? (
                      <p className="mt-1 text-xs text-ink-muted">{row.reviewer_note}</p>
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
        <div className="flex flex-wrap justify-between gap-3 text-sm text-ink-muted">
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
