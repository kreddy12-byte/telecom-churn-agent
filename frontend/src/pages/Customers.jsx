import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import PageHeader from "../components/common/PageHeader";
import ErrorBanner from "../components/common/ErrorBanner";
import EmptyState from "../components/common/EmptyState";
import { TableSkeleton } from "../components/common/Skeleton";
import Button from "../components/common/Button";
import CustomerTable from "../components/customers/CustomerTable";
import { formatPageRange } from "../utils/format";
import { apiErrorMessage, getCustomers } from "../services/api";

const PAGE_SIZE = 20;

export default function Customers() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const q = params.get("q") || "";
  const riskLevel = params.get("risk_level") || params.get("risk") || "";
  const offset = Number(params.get("offset") || 0);

  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [draft, setDraft] = useState(q);

  function load() {
    setError(null);
    getCustomers({
      limit: PAGE_SIZE,
      offset,
      q: q || undefined,
      riskLevel: riskLevel || undefined,
    })
      .then(setData)
      .catch((err) => setError(apiErrorMessage(err)));
  }

  useEffect(() => {
    load();
  }, [q, riskLevel, offset]);

  function applySearch(event) {
    event.preventDefault();
    const next = draft.trim();
    // Exact Telco IDs open the intelligence page directly. A missing
    // customer is handled there instead of waiting on a pre-flight GET.
    if (/^[A-Z0-9]{4}-[A-Z0-9]{5}$/i.test(next)) {
      navigate(`/customers/${next.toUpperCase()}`);
      return;
    }
    setParams({
      ...(next ? { q: next } : {}),
      ...(riskLevel ? { risk_level: riskLevel } : {}),
    });
  }

  const total = data?.meta?.total ?? 0;
  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  return (
    <div>
      <PageHeader
        title="Customers"
        description="Stored Telco profiles. Open a customer to view intelligence and record a retention decision."
      />

      <form onSubmit={applySearch} className="mb-4 flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block text-ink-muted">Customer ID</span>
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="7590-VHVEG"
            className="field-input w-56"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-ink-muted">Risk</span>
          <select
            value={riskLevel}
            onChange={(event) =>
              setParams({
                ...(q ? { q } : {}),
                ...(event.target.value ? { risk_level: event.target.value } : {}),
              })
            }
            className="field-input w-44"
          >
            <option value="">All stored bands</option>
            <option value="HIGH">HIGH</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="LOW">LOW</option>
          </select>
        </label>
        <Button type="submit" variant="primary">
          Search
        </Button>
      </form>

      {error ? <ErrorBanner message={error} onRetry={load} /> : null}
      {!data && !error ? <TableSkeleton /> : null}
      {data && data.items.length === 0 ? (
        <EmptyState
          title="No customers match this view"
          body="Seed the database or clear the search filters."
        />
      ) : null}
      {data && data.items.length > 0 ? <CustomerTable items={data.items} /> : null}

      {data ? (
        <div className="mt-4 flex items-center justify-between text-sm text-ink-muted">
          <p>{formatPageRange(total, offset, PAGE_SIZE)}</p>
          <div className="flex gap-2">
            <Button
              disabled={!canPrev}
              onClick={() =>
                setParams({
                  ...(q ? { q } : {}),
                  ...(riskLevel ? { risk_level: riskLevel } : {}),
                  offset: String(Math.max(0, offset - PAGE_SIZE)),
                })
              }
            >
              Previous
            </Button>
            <Button
              disabled={!canNext}
              onClick={() =>
                setParams({
                  ...(q ? { q } : {}),
                  ...(riskLevel ? { risk_level: riskLevel } : {}),
                  offset: String(offset + PAGE_SIZE),
                })
              }
            >
              Next
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
