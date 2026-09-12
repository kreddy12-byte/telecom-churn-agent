import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../components/common/PageHeader";
import ErrorBanner from "../components/common/ErrorBanner";
import EmptyState from "../components/common/EmptyState";
import MetricCard from "../components/common/MetricCard";
import SectionCard from "../components/common/SectionCard";
import WorkflowStrip from "../components/common/WorkflowStrip";
import Button from "../components/common/Button";
import {
  ChartSkeleton,
  KpiSkeleton,
  TableSkeleton,
} from "../components/common/Skeleton";
import { PriorityRankingTable } from "../components/customers/CustomerTable";
import {
  RiskDistributionChart,
  RiskPriorityPanel,
} from "../components/dashboard/RiskOverview";
import RetentionPriorityPanel from "../components/dashboard/RetentionPriorityPanel";
import {
  getGlobalImportance,
  getOverview,
  getPredictionDistribution,
  getPredictionRanking,
  getPredictionSummary,
  runBatchPredictions,
} from "../services/api";
import { formatCount, formatDate, formatPercent } from "../utils/format";

const ProbabilityDistributionChart = lazy(() =>
  import("../components/dashboard/ProbabilityDistributionChart")
);
const ChurnDriversChart = lazy(() =>
  import("../components/dashboard/ChurnDriversChart")
);

const RANKING_UNAVAILABLE =
  "High-risk ranking is not available. Open the customer list to continue review.";
const DISTRIBUTION_UNAVAILABLE =
  "Churn probability distribution is not available. The rest of the dashboard is still usable.";
const DRIVERS_UNAVAILABLE =
  "Global SHAP importance is not available. Customer-level explanations still work from the intelligence page.";

export default function Overview() {
  const [overview, setOverview] = useState(null);
  const [summary, setSummary] = useState(null);
  const [ranking, setRanking] = useState(null);
  const [distribution, setDistribution] = useState(null);
  const [drivers, setDrivers] = useState(null);
  const [sectionErrors, setSectionErrors] = useState({});
  const [error, setError] = useState(null);
  const [scoring, setScoring] = useState(false);
  const [batchNotice, setBatchNotice] = useState(null);
  const scoringRef = useRef(false);

  function loadDashboard() {
    setError(null);
    setSectionErrors({});

    const core = Promise.all([getOverview(), getPredictionSummary()])
      .then(([overviewData, summaryData]) => {
        setOverview(overviewData);
        setSummary(summaryData);
      })
      .catch(() => {
        setError("Unable to load churn intelligence.");
      });

    const rankingLoad = getPredictionRanking({ risk: "HIGH", limit: 10, offset: 0 })
      .then((data) => setRanking(data))
      .catch(() => {
        setSectionErrors((current) => ({ ...current, ranking: RANKING_UNAVAILABLE }));
      });

    const distributionLoad = getPredictionDistribution()
      .then((data) => setDistribution(data))
      .catch(() => {
        setSectionErrors((current) => ({
          ...current,
          distribution: DISTRIBUTION_UNAVAILABLE,
        }));
      });

    const driversLoad = getGlobalImportance(8)
      .then((data) => setDrivers(data))
      .catch(() => {
        setSectionErrors((current) => ({ ...current, drivers: DRIVERS_UNAVAILABLE }));
      });

    return Promise.all([core, rankingLoad, distributionLoad, driversLoad]);
  }

  useEffect(() => {
    loadDashboard();
  }, []);

  async function handleBatchScore() {
    if (scoringRef.current) {
      return;
    }
    scoringRef.current = true;
    setScoring(true);
    setBatchNotice(null);
    try {
      const result = await runBatchPredictions();
      await loadDashboard();
      const processed = Number(result?.processed) || 0;
      setBatchNotice({
        tone: "ok",
        text: `Scored ${formatCount(processed)} customers. Priority list updated.`,
        scoredAt: result?.scored_at || null,
      });
    } catch {
      setBatchNotice({
        tone: "err",
        text: "Unable to score the customer base. Please try again.",
      });
    } finally {
      scoringRef.current = false;
      setScoring(false);
    }
  }

  const hasScores = Boolean(summary && summary.total_scored > 0);
  const latestScoredAt =
    batchNotice?.scoredAt || ranking?.items?.[0]?.predicted_at || null;
  const scoredTotal = summary?.total_scored ?? 0;
  const pendingReviews = overview?.action_counts?.PENDING;

  const header = (
    <PageHeader
      title="Customer Retention Overview"
      description="Summarize churn risk across the customer base, surface priority accounts, and move from prediction to retention decisions."
      actions={
        <Button
          variant="primary"
          onClick={handleBatchScore}
          disabled={scoring}
          aria-busy={scoring}
        >
          {scoring ? "Scoring customer base..." : "Run Batch Prediction"}
        </Button>
      }
    />
  );

  if (error && (!overview || !summary)) {
    return (
      <div className="space-y-5">
        {header}
        <ErrorBanner message={error} onRetry={loadDashboard} />
      </div>
    );
  }

  if (!overview || !summary) {
    return (
      <div className="space-y-5">
        {header}
        <p className="muted" role="status">
          Loading churn intelligence...
        </p>
        <KpiSkeleton count={3} />
        <div className="grid gap-4 lg:grid-cols-2">
          <ChartSkeleton />
          <ChartSkeleton className="h-40" />
        </div>
        <TableSkeleton rows={5} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {header}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <WorkflowStrip current="Predict" />
        <p className="max-w-xl text-sm leading-6 text-ink-muted">
          Review the high-risk priority queue, then open a customer to explain
          the prediction, recommend a retention action, simulate interventions,
          and record a human decision.
        </p>
      </div>

      {batchNotice ? (
        <div
          role="status"
          className={
            batchNotice.tone === "err"
              ? "rounded-panel border border-danger/35 bg-danger-soft px-4 py-3 text-sm text-danger ri-enter"
              : "rounded-panel border border-success/35 bg-success-soft px-4 py-3 text-sm text-success ri-enter"
          }
        >
          {batchNotice.text}
        </div>
      ) : null}

      {error ? <ErrorBanner message={error} onRetry={loadDashboard} /> : null}

      <section aria-labelledby="executive-summary-heading" className="space-y-3 ri-enter">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <h2 id="executive-summary-heading" className="section-title">
            Executive summary
          </h2>
          {latestScoredAt ? (
            <p className="text-xs text-ink-faint">
              Latest scores recorded {formatDate(latestScoredAt)}
            </p>
          ) : null}
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <MetricCard
            label="Total customers"
            value={formatCount(overview.customer_count)}
            hint="Stored Telco records, not a model output."
          />
          {hasScores ? (
            <>
              <MetricCard
                label="Customers scored"
                value={formatCount(summary.total_scored)}
                hint="Customers with a stored prediction."
              />
              <MetricCard
                label="High risk"
                value={formatCount(summary.risk_counts?.HIGH)}
                hint="Latest prediction per customer."
                tone="high"
              />
              <MetricCard
                label="Medium risk"
                value={formatCount(summary.risk_counts?.MEDIUM)}
                hint="Predicted probability band, not a guarantee of churn."
                tone="medium"
              />
              <MetricCard
                label="Low risk"
                value={formatCount(summary.risk_counts?.LOW)}
                tone="low"
              />
              <MetricCard
                label="Average churn probability"
                value={formatPercent(summary.average_churn_probability)}
                hint="Predicted likelihood of churn, not model accuracy or ROC-AUC."
              />
              {pendingReviews != null ? (
                <MetricCard
                  label="Pending reviews"
                  value={formatCount(pendingReviews)}
                  hint="Retention decisions awaiting reviewer approval."
                />
              ) : null}
            </>
          ) : null}
        </div>
      </section>

      {hasScores ? (
        <p className="text-xs leading-5 text-ink-muted">
          Customer counts are headcount. Churn probability is the model&apos;s
          predicted risk. Model ROC-AUC and accuracy are training metrics and
          live on{" "}
          <Link to="/model" className="text-accent hover:underline">
            Model Intelligence
          </Link>
          .
          {latestScoredAt ? ` Latest scores recorded ${formatDate(latestScoredAt)}.` : ""}
        </p>
      ) : (
        <EmptyState
          title="Prediction data is not available yet."
          body="Run batch prediction to populate the dashboard."
        />
      )}

      {!hasScores ? (
        <p className="text-sm">
          <Link to="/customers" className="text-accent hover:underline">
            View all customers
          </Link>
        </p>
      ) : null}

      {hasScores ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard
            kicker="Risk"
            title="Customer Risk Distribution"
            description="Share of scored customers in each predicted risk band. Latest prediction per customer."
            elevated
          >
            <RiskDistributionChart
              counts={summary.risk_counts}
              total={scoredTotal}
            />
          </SectionCard>
          <SectionCard
            kicker="Priority"
            title="Risk priority"
            description="Use the HIGH band to order investigation, not to assume every customer will leave."
          >
            <RiskPriorityPanel counts={summary.risk_counts} total={scoredTotal} />
          </SectionCard>
        </div>
      ) : null}

      {hasScores ? (
        <SectionCard
          kicker="Probability"
          title="Churn Probability Distribution"
          description="Counts of latest predicted probabilities in 10-point bands. This uses stored scores, not risk labels."
        >
          {sectionErrors.distribution ? (
            <p className="muted">{sectionErrors.distribution}</p>
          ) : !distribution ? (
            <ChartSkeleton />
          ) : (
            <Suspense fallback={<ChartSkeleton />}>
              <ProbabilityDistributionChart buckets={distribution.buckets} />
            </Suspense>
          )}
        </SectionCard>
      ) : null}

      {hasScores ? (
        <SectionCard
          kicker="Priority queue"
          title="Top High-Risk Customers"
          description="Customers with the highest predicted churn probability. Open one to view intelligence and decide what to do."
          elevated
          actions={
            <div className="flex flex-wrap gap-3 text-sm">
              <Link
                to="/customers?risk_level=HIGH"
                className="font-medium text-accent hover:underline"
              >
                View high-risk customers
              </Link>
              <Link to="/customers" className="font-medium text-accent hover:underline">
                View all customers
              </Link>
            </div>
          }
        >
          {sectionErrors.ranking ? (
            <p className="muted">{sectionErrors.ranking}</p>
          ) : !ranking ? (
            <TableSkeleton rows={5} />
          ) : ranking.items?.length ? (
            <div className="ri-enter">
              <PriorityRankingTable items={ranking.items} />
            </div>
          ) : (
            <p className="muted">
              No high-risk customers in the latest scores. Review the full
              customer list.
            </p>
          )}
        </SectionCard>
      ) : null}

      {hasScores ? (
        <SectionCard
          kicker="Model signals"
          title="Top Churn Drivers"
          description="Stored global SHAP ranking from the trained model. Not recomputed on this page."
        >
          {sectionErrors.drivers ? (
            <p className="muted">{sectionErrors.drivers}</p>
          ) : !drivers ? (
            <ChartSkeleton />
          ) : (
            <Suspense fallback={<ChartSkeleton />}>
              <ChurnDriversChart drivers={drivers.drivers} />
            </Suspense>
          )}
        </SectionCard>
      ) : null}

      <SectionCard
        kicker="Workflow"
        title="Retention Priority"
        description="Predicted risk orders investigation. The model does not execute retention actions."
        elevated
      >
        <RetentionPriorityPanel />
      </SectionCard>
    </div>
  );
}
