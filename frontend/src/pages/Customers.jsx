import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import PageHeader from "../components/common/PageHeader";
import ErrorBanner from "../components/common/ErrorBanner";
import EmptyState from "../components/common/EmptyState";
import { TableSkeleton } from "../components/common/Skeleton";
import Button from "../components/common/Button";
import SearchInput from "../components/common/SearchInput";
import Select from "../components/common/Select";
import ProgressBar from "../components/common/ProgressBar";
import CustomerTable from "../components/customers/CustomerTable";
import { formatCount, formatPageRange } from "../utils/format";
import { apiErrorMessage, getCustomers } from "../services/api";
import { riskToneBorder, riskToneSurface } from "../utils/risk";

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
    return getCustomers({
      limit: PAGE_SIZE,
      offset,
      q: q || undefined,
      riskLevel: riskLevel || undefined,
    })
      .then(setData)
      .catch((err) => setError(apiErrorMessage(err)));
  }

  useEffect(() => {
    let cancelled = false;
    setError(null);
    getCustomers({
      limit: PAGE_SIZE,
      offset,
      q: q || undefined,
      riskLevel: riskLevel || undefined,
    })
      .then((next) => {
        if (!cancelled) setData(next);
      })
      .catch((err) => {
        if (!cancelled) setError(apiErrorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [q, riskLevel, offset]);

  useEffect(() => {
    setDraft(q);
  }, [q]);

  function applySearch(event) {
    event.preventDefault();
    const next = draft.trim();
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

  const pageRiskSummary = useMemo(() => {
    if (!data?.items?.length) return null;
    const counts = { HIGH: 0, MEDIUM: 0, LOW: 0, NONE: 0 };
    data.items.forEach((row) => {
      const level = row.latest_prediction?.risk_level;
      if (level === "HIGH" || level === "MEDIUM" || level === "LOW") {
        counts[level] += 1;
      } else {
        counts.NONE += 1;
      }
    });
    return counts;
  }, [data]);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Customer Intelligence"
        description="Identify high-risk customers, understand their churn signals, and prioritize retention opportunities."
      />

      <form
        onSubmit={applySearch}
        className="toolbar-surface flex flex-wrap items-end gap-3 px-4 py-4"
      >
        <label className="min-w-[12rem] flex-1 text-sm">
          <span className="label-text mb-1.5 block">Customer ID</span>
          <SearchInput
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Search or open 7590-VHVEG"
            aria-label="Customer ID"
          />
        </label>
        <label className="w-full text-sm sm:w-44">
          <span className="label-text mb-1.5 block">Risk</span>
          <Select
            value={riskLevel}
            onChange={(event) =>
              setParams({
                ...(q ? { q } : {}),
                ...(event.target.value ? { risk_level: event.target.value } : {}),
              })
            }
            aria-label="Risk filter"
          >
            <option value="">All stored bands</option>
            <option value="HIGH">HIGH</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="LOW">LOW</option>
          </Select>
        </label>
        <Button type="submit" variant="primary">
          Search
        </Button>
      </form>

      {pageRiskSummary && data?.items?.length ? (
        <section
          className="grid gap-3 sm:grid-cols-3"
          aria-label="Risk mix on this page"
        >
          {[
            { key: "HIGH", label: "High risk on page", tone: "high", value: pageRiskSummary.HIGH },
            { key: "MEDIUM", label: "Medium risk on page", tone: "medium", value: pageRiskSummary.MEDIUM },
            { key: "LOW", label: "Low risk on page", tone: "low", value: pageRiskSummary.LOW },
          ].map((row) => (
            <div
              key={row.key}
              className={`surface border-l-[3px] px-4 py-3 ${riskToneBorder(row.tone)} ${riskToneSurface(row.tone)}`}
            >
              <p className="meta">{row.label}</p>
              <p className="mt-1.5 text-lg font-semibold tabular-nums text-ink">
                {formatCount(row.value)}
              </p>
              <ProgressBar
                className="mt-2"
                value={row.value}
                max={data.items.length || 1}
                tone={row.tone}
                label={`${row.label}: ${row.value}`}
              />
            </div>
          ))}
        </section>
      ) : null}

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
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-ink-muted">
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
