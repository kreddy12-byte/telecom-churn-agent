import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../components/common/PageHeader";
import ErrorBanner from "../components/common/ErrorBanner";
import EmptyState from "../components/common/EmptyState";
import MetricCard from "../components/common/MetricCard";
import SectionCard from "../components/common/SectionCard";
import Button from "../components/common/Button";
import Badge from "../components/common/Badge";
import {
  KpiSkeleton,
  ChartSkeleton,
  TableSkeleton,
  BatchAnalysisSkeleton,
} from "../components/common/Skeleton";
import LoadingState from "../components/common/LoadingState";
import { PriorityRankingTable } from "../components/customers/CustomerTable";
import {
  apiErrorMessage,
  getModelInfo,
  getOverview,
  getPredictionDistribution,
  getPredictionRanking,
  getPredictionSummary,
  runBatchPredictions,
} from "../services/api";
import { formatCount, formatDate, formatPercent, formatShare } from "../utils/format";

const RiskDistributionChart = lazy(() =>
  import("../components/dashboard/RiskOverview").then((module) => ({
    default: module.RiskDistributionChart,
  }))
);
const RiskPriorityPanel = lazy(() =>
  import("../components/dashboard/RiskOverview").then((module) => ({
    default: module.RiskPriorityPanel,
  }))
);
const ProbabilityDistributionChart = lazy(() =>
  import("../components/dashboard/ProbabilityDistributionChart")
);

const STATUS = {
  LOADING: "loading",
  READY: "ready",
  RUNNING: "running",
  COMPLETED: "completed",
  FAILED: "failed",
};

export default function BatchAnalysis() {
  const [overview, setOverview] = useState(null);
  const [summary, setSummary] = useState(null);
  const [distribution, setDistribution] = useState(null);
  const [ranking, setRanking] = useState(null);
  const [model, setModel] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [runError, setRunError] = useState(null);
  const [phase, setPhase] = useState(STATUS.LOADING);
  const [lastRun, setLastRun] = useState(null);
  const runningRef = useRef(false);

  function loadWorkspace({ preservePhase = false } = {}) {
    setLoadError(null);

    return getOverview()
      .then(async (overviewData) => {
        setOverview(overviewData);
        if (!preservePhase) {
          setPhase(STATUS.READY);
        }

        // Secondary panels load in parallel and must not block dataset readiness.
        const [summaryResult, distributionResult, rankingResult, modelResult] =
          await Promise.allSettled([
            getPredictionSummary(),
            getPredictionDistribution(),
            getPredictionRanking({ risk: "HIGH", limit: 10, offset: 0 }),
            getModelInfo(),
          ]);

        if (summaryResult.status === "fulfilled") {
          setSummary(summaryResult.value);
        } else {
          setSummary(null);
        }

        if (distributionResult.status === "fulfilled") {
          setDistribution(distributionResult.value);
        } else {
          setDistribution(null);
        }

        if (rankingResult.status === "fulfilled") {
          setRanking(rankingResult.value);
        } else {
          setRanking(null);
        }

        setModel(modelResult.status === "fulfilled" ? modelResult.value : null);
      })
      .catch((err) => {
        setLoadError(apiErrorMessage(err) || "Unable to load batch analysis.");
        if (!preservePhase) {
          setPhase(STATUS.FAILED);
        }
        throw err;
      });
  }

  useEffect(() => {
    loadWorkspace().catch(() => {});
  }, []);

  async function handleRun() {
    if (runningRef.current) return;
    runningRef.current = true;
    setPhase(STATUS.RUNNING);
    setRunError(null);
    try {
      const result = await runBatchPredictions();
      setLastRun(result);
      await loadWorkspace({ preservePhase: true });
      setPhase(STATUS.COMPLETED);
    } catch (err) {
      setRunError(apiErrorMessage(err) || "Batch analysis could not be completed.");
      setPhase(STATUS.FAILED);
    } finally {
      runningRef.current = false;
    }
  }

  const customerCount = overview?.customer_count ?? 0;
  const hasPopulation = customerCount > 0;
  const hasScores = Boolean(summary && summary.total_scored > 0);
  const scoredTotal = summary?.total_scored ?? 0;
  const highCount = summary?.risk_counts?.HIGH ?? 0;
  const mediumCount = summary?.risk_counts?.MEDIUM ?? 0;
  const lowCount = summary?.risk_counts?.LOW ?? 0;
  const highShare = hasScores ? formatShare(highCount, scoredTotal) : null;
  const readyToRun = hasPopulation && phase !== STATUS.RUNNING && phase !== STATUS.LOADING;
  const latestScoredAt =
    lastRun?.scored_at || ranking?.items?.[0]?.predicted_at || null;

  const statusBadge =
    phase === STATUS.RUNNING
      ? { tone: "info", label: "Running" }
      : phase === STATUS.COMPLETED
        ? { tone: "success", label: "Completed" }
        : phase === STATUS.FAILED
          ? { tone: "danger", label: "Failed" }
          : hasScores
            ? { tone: "accent", label: "Ready · prior results available" }
            : { tone: "neutral", label: "Ready" };

  if (phase === STATUS.LOADING && !overview) {
    return (
      <div className="space-y-5">
        <PageHeader
          title="Batch Analysis"
          description="Analyze your customer population and identify the highest-priority churn risks."
        />
        <BatchAnalysisSkeleton />
      </div>
    );
  }

  if (loadError && !overview) {
    return (
      <div className="space-y-5">
        <PageHeader
          title="Batch Analysis"
          description="Analyze your customer population and identify the highest-priority churn risks."
        />
        <ErrorBanner message={loadError} onRetry={loadWorkspace} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Batch Analysis"
        description="Analyze your customer population and identify the highest-priority churn risks."
      />

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <SectionCard
          kicker="Dataset"
          title="Customer population"
          description="Scores the connected Telco customer database with the saved production model. This is not an uploaded file workflow."
          elevated
        >
          <dl className="grid gap-4 sm:grid-cols-2">
            <div>
              <dt className="meta">Source</dt>
              <dd className="mt-1 text-sm font-semibold text-ink">Connected customer database</dd>
            </div>
            <div>
              <dt className="meta">Records</dt>
              <dd className="mt-1 text-2xl font-semibold tabular-nums text-ink">
                {formatCount(customerCount)}
              </dd>
            </div>
            <div>
              <dt className="meta">Schema</dt>
              <dd className="mt-1 text-sm font-medium text-ink">Telco customer model</dd>
            </div>
            <div>
              <dt className="meta">Population status</dt>
              <dd className="mt-1">
                {hasPopulation ? (
                  <Badge tone="success">Ready for analysis</Badge>
                ) : (
                  <Badge tone="warning">No customers loaded</Badge>
                )}
              </dd>
            </div>
          </dl>
          <p className="mt-4 text-sm leading-6 text-ink-muted">
            Batch analysis scores every stored customer with the same predictor used by
            single-customer prediction. It does not retrain the model and does not accept
            arbitrary CSV uploads.
          </p>
        </SectionCard>

        <SectionCard
          kicker="Future capability"
          title="Uploaded dataset"
          description="Arbitrary file upload is not available in the current API."
        >
          <div className="rounded-panel border border-dashed border-line bg-surface-muted/60 px-4 py-5">
            <p className="text-sm font-semibold text-ink">CSV upload not supported yet</p>
            <p className="mt-2 text-sm leading-6 text-ink-muted">
              A future release can add dataset validation and upload against a dedicated
              endpoint. This workspace currently analyzes the connected customer population
              only.
            </p>
            <button
              type="button"
              disabled
              className="mt-4 inline-flex cursor-not-allowed items-center rounded-control border border-line px-3 py-1.5 text-sm text-ink-disabled"
            >
              Upload dataset (unavailable)
            </button>
          </div>
        </SectionCard>
      </section>

      <SectionCard
        kicker="Analysis"
        title="Run batch analysis"
        description="Score the full customer population, then refresh risk distribution and the priority queue."
        actions={<Badge tone={statusBadge.tone}>{statusBadge.label}</Badge>}
        elevated
      >
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl space-y-2 text-sm leading-6 text-ink-muted">
            {phase === STATUS.RUNNING ? (
              <p role="status">
                Analyzing customer population… This can take a few minutes for large bases.
                Progress percentage is not reported by the API.
              </p>
            ) : phase === STATUS.COMPLETED && lastRun ? (
              <p role="status">
                Analysis completed. {formatCount(lastRun.processed)} customers analyzed
                {lastRun.scored_at ? ` at ${formatDate(lastRun.scored_at)}` : ""}.
                {lastRun.model_version ? ` Model ${lastRun.model_version}.` : ""}
              </p>
            ) : hasPopulation ? (
              <p>
                Ready to score {formatCount(customerCount)} stored customers with the
                production churn model
                {model?.model_name ? ` (${model.model_name}` : ""}
                {model?.model_version ? ` ${model.model_version}` : ""}
                {model?.model_name ? ")" : ""}.
              </p>
            ) : (
              <p>Load customers into the database before running batch analysis.</p>
            )}
            {latestScoredAt && phase !== STATUS.RUNNING ? (
              <p className="text-xs text-ink-faint">
                Latest stored scores: {formatDate(latestScoredAt)}
              </p>
            ) : null}
          </div>
          <Button
            variant="primary"
            size="lg"
            onClick={handleRun}
            disabled={!readyToRun}
            aria-busy={phase === STATUS.RUNNING}
          >
            {phase === STATUS.RUNNING ? "Analyzing…" : "Run Batch Analysis"}
          </Button>
        </div>

        {phase === STATUS.RUNNING ? (
          <div className="mt-5 rounded-panel border border-info/30 bg-info-soft px-4 py-4">
            <LoadingState label="Scoring stored customers with the production model…" />
          </div>
        ) : null}

        {runError ? (
          <div className="mt-4">
            <ErrorBanner message={runError} onRetry={handleRun} />
          </div>
        ) : null}
      </SectionCard>

      {model ? (
        <SectionCard
          kicker="Model context"
          title="Production predictor"
          description="Compact facts from the locked training artifacts."
          variant="model"
        >
          <dl className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="meta">Model</dt>
              <dd className="mt-1 font-semibold text-ink">{model.model_name || "—"}</dd>
            </div>
            <div>
              <dt className="meta">Version</dt>
              <dd className="mt-1 font-semibold text-ink">{model.model_version || "—"}</dd>
            </div>
            <div>
              <dt className="meta">Purpose</dt>
              <dd className="mt-1 font-medium text-ink">
                {model.target || "Churn probability estimation"}
              </dd>
            </div>
            <div>
              <dt className="meta">Explainability</dt>
              <dd className="mt-1 font-medium text-ink">{model.explainability || "—"}</dd>
            </div>
          </dl>
          <p className="mt-3 text-sm">
            <Link to="/model" className="font-medium text-accent hover:underline">
              View full model information
            </Link>
          </p>
        </SectionCard>
      ) : null}

      {!hasScores ? (
        <EmptyState
          title="No batch analysis yet"
          body={
            hasPopulation
              ? `Your customer population (${formatCount(customerCount)} records) is ready to be analyzed.`
              : "No customers are available in the connected database yet."
          }
        />
      ) : (
        <>
          <section aria-labelledby="batch-results-heading" className="space-y-3 ri-enter">
            <h2 id="batch-results-heading" className="section-title">
              Results
            </h2>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <MetricCard
                label="Total analyzed"
                value={formatCount(scoredTotal)}
                hint="Customers with a latest stored prediction."
              />
              <MetricCard
                label="High risk"
                value={formatCount(highCount)}
                hint={highShare ? `${highShare} of scored customers.` : undefined}
                tone="high"
              />
              <MetricCard
                label="Medium risk"
                value={formatCount(mediumCount)}
                tone="medium"
              />
              <MetricCard
                label="Low risk"
                value={formatCount(lowCount)}
                tone="low"
              />
              <MetricCard
                label="Average churn probability"
                value={formatPercent(summary.average_churn_probability)}
                hint="Predicted likelihood of churn, not model accuracy."
              />
              <MetricCard
                label="High-risk share"
                value={highShare || "—"}
                hint="Share of scored customers in the HIGH band."
                tone="high"
              />
            </div>
          </section>

          <div className="grid gap-4 lg:grid-cols-2">
            <SectionCard
              kicker="Risk"
              title="Risk distribution"
              description="Share of scored customers in each predicted risk band."
            >
              <Suspense fallback={<ChartSkeleton />}>
                <RiskDistributionChart
                  counts={summary.risk_counts}
                  total={scoredTotal}
                />
              </Suspense>
            </SectionCard>
            <SectionCard
              kicker="Priority"
              title="Risk priority"
              description="Use the HIGH band to order investigation."
            >
              <Suspense fallback={<ChartSkeleton className="h-40" />}>
                <RiskPriorityPanel counts={summary.risk_counts} total={scoredTotal} />
              </Suspense>
            </SectionCard>
          </div>

          <SectionCard
            kicker="Probability"
            title="Churn probability distribution"
            description="Histogram of latest predicted probabilities in 10-point bands."
          >
            {!distribution ? (
              <ChartSkeleton />
            ) : (
              <Suspense fallback={<ChartSkeleton />}>
                <ProbabilityDistributionChart buckets={distribution.buckets} />
              </Suspense>
            )}
          </SectionCard>

          <SectionCard
            kicker="Priority queue"
            title="Priority customers"
            description="Highest predicted churn probability from the latest scores."
            actions={
              <Link
                to="/customers?risk_level=HIGH"
                className="text-sm font-medium text-accent hover:underline"
              >
                View high-risk customers
              </Link>
            }
          >
            {!ranking ? (
              <TableSkeleton rows={5} />
            ) : ranking.items?.length ? (
              <PriorityRankingTable items={ranking.items} />
            ) : (
              <p className="muted">No high-risk customers in the latest scores.</p>
            )}
          </SectionCard>
        </>
      )}
    </div>
  );
}
