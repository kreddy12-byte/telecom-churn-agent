import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../components/common/PageHeader";
import ErrorBanner from "../components/common/ErrorBanner";
import EmptyState from "../components/common/EmptyState";
import MetricCard from "../components/common/MetricCard";
import SectionCard from "../components/common/SectionCard";
import WorkflowStrip from "../components/common/WorkflowStrip";
import Button from "../components/common/Button";
import { PriorityRankingTable } from "../components/customers/CustomerTable";
import {
  RiskDistributionChart,
  RiskPriorityPanel,
} from "../components/dashboard/RiskOverview";
import ProbabilityDistributionChart from "../components/dashboard/ProbabilityDistributionChart";
import ChurnDriversChart from "../components/dashboard/ChurnDriversChart";
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

  // 1. LOAD DASHBOARD DATA
  // Overview + summary are required for the executive cards. Ranking, the
  // probability histogram, and global SHAP drivers load independently so one
  // visualization outage cannot blank the page. Batch scoring is never started
  // here — only the explicit reviewer click below may call POST /predictions/batch.
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

    // Optional section failures are swallowed above so a histogram outage
    // cannot reject this promise and blank the executive cards.
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

  const header = (
    <PageHeader
      title="Overview"
      description="Here are the customers most likely to churn, and here is where you investigate and decide what to do."
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
      <div>
        {header}
        <ErrorBanner message={error} onRetry={loadDashboard} />
      </div>
    );
  }

  if (!overview || !summary) {
    return (
      <div>
        {header}
        <p className="muted" role="status">
          Loading churn intelligence...
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {header}
      <WorkflowStrip current="Predict" />
      <p className="text-sm text-ink-muted">
        Review the high-risk priority queue, then open a customer to explain
        the prediction, recommend a retention action, simulate interventions,
        and record a human decision.
      </p>

      {batchNotice ? (
        <div
          role="status"
          className={
            batchNotice.tone === "err"
              ? "rounded-panel border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900"
              : "rounded-panel border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900"
          }
        >
          {batchNotice.text}
        </div>
      ) : null}

      {error ? <ErrorBanner message={error} onRetry={loadDashboard} /> : null}

      {/* 2. BUILD RISK SUMMARY */}
      <section aria-labelledby="executive-summary-heading">
        <h2 id="executive-summary-heading" className="section-title mb-3">
          Executive summary
        </h2>
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
            Model information
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
            title="Customer Risk Distribution"
            description="Share of scored customers in each predicted risk band. Latest prediction per customer."
          >
            <RiskDistributionChart
              counts={summary.risk_counts}
              total={scoredTotal}
            />
          </SectionCard>
          <SectionCard
            title="Risk priority"
            description="Use the HIGH band to order investigation, not to assume every customer will leave."
          >
            <RiskPriorityPanel counts={summary.risk_counts} total={scoredTotal} />
          </SectionCard>
        </div>
      ) : null}

      {/* 3. BUILD CHART DATA — histogram buckets come from SQL aggregation. */}
      {hasScores ? (
        <SectionCard
          title="Churn Probability Distribution"
          description="Counts of latest predicted probabilities in 10-point bands. This uses stored scores, not risk labels."
        >
          {sectionErrors.distribution ? (
            <p className="muted">{sectionErrors.distribution}</p>
          ) : !distribution ? (
            <p className="muted" role="status">
              Loading probability distribution...
            </p>
          ) : (
            <ProbabilityDistributionChart buckets={distribution.buckets} />
          )}
        </SectionCard>
      ) : null}

      {/* 4. RENDER PRIORITY QUEUE */}
      {hasScores ? (
        <SectionCard
          title="Top High-Risk Customers"
          description="Customers with the highest predicted churn probability. Open one to view intelligence and decide what to do."
          actions={
            <div className="flex flex-wrap gap-3 text-sm">
              <Link
                to="/customers?risk_level=HIGH"
                className="text-accent hover:underline"
              >
                View high-risk customers
              </Link>
              <Link to="/customers" className="text-accent hover:underline">
                View all customers
              </Link>
            </div>
          }
        >
          {sectionErrors.ranking ? (
            <p className="muted">{sectionErrors.ranking}</p>
          ) : !ranking ? (
            <p className="muted" role="status">
              Loading priority customers...
            </p>
          ) : ranking.items?.length ? (
            <PriorityRankingTable items={ranking.items} />
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
          title="Top Churn Drivers"
          description="Stored global SHAP ranking from the trained model. Not recomputed on this page."
        >
          {sectionErrors.drivers ? (
            <p className="muted">{sectionErrors.drivers}</p>
          ) : !drivers ? (
            <p className="muted" role="status">
              Loading churn drivers...
            </p>
          ) : (
            <ChurnDriversChart drivers={drivers.drivers} />
          )}
        </SectionCard>
      ) : null}

      <SectionCard
        title="Retention Priority"
        description="Predicted risk orders investigation. The model does not execute retention actions."
      >
        <RetentionPriorityPanel />
      </SectionCard>
    </div>
  );
}
