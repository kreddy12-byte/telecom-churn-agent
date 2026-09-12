import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import DecisionPanel from "../components/actions/DecisionPanel";
import ErrorBanner from "../components/common/ErrorBanner";
import Button from "../components/common/Button";
import PageHeader from "../components/common/PageHeader";
import RiskBadge from "../components/common/RiskBadge";
import SectionCard from "../components/common/SectionCard";
import WorkflowStrip from "../components/common/WorkflowStrip";
import { CustomerIntelligenceSkeleton } from "../components/common/Skeleton";
import ShapBars from "../components/explanation/ShapBars";
import RecommendationPanel from "../components/retention/RecommendationPanel";
import WhatIfPanel from "../components/simulator/WhatIfPanel";
import { useCustomerIntelligence } from "../hooks/useCustomerIntelligence";
import { formatMoney, formatPercent } from "../utils/format";

const PROFILE_PRIMARY = [
  ["Tenure", (c) => (c.tenure != null ? `${c.tenure} month${c.tenure === 1 ? "" : "s"}` : "—")],
  ["Contract Type", (c) => c.contract],
  ["Internet Service", (c) => c.internet_service],
  ["Monthly Charges", (c) => formatMoney(c.monthly_charges)],
  ["Total Charges", (c) => formatMoney(c.total_charges)],
  ["Payment Method", (c) => c.payment_method],
  ["Tech Support", (c) => c.tech_support],
  ["Online Security", (c) => c.online_security],
];

const PROFILE_FULL = [
  ["Gender", (c) => c.gender],
  ["Senior Citizen", (c) => (c.senior_citizen ? "Yes" : "No")],
  ["Partner", (c) => c.partner],
  ["Dependents", (c) => c.dependents],
  ["Phone Service", (c) => c.phone_service],
  ["Multiple Lines", (c) => c.multiple_lines],
  ["Online Backup", (c) => c.online_backup],
  ["Device Protection", (c) => c.device_protection],
  ["Streaming TV", (c) => c.streaming_tv],
  ["Streaming Movies", (c) => c.streaming_movies],
  ["Paperless Billing", (c) => c.paperless_billing],
];

export default function CustomerIntelligence() {
  const { customerId } = useParams();
  const intel = useCustomerIntelligence(customerId);
  const [showFull, setShowFull] = useState(false);

  const probability =
    intel.prediction?.churn_probability ?? intel.explanation?.churn_probability;
  const risk = intel.prediction?.risk_level ?? intel.explanation?.risk_level;
  const version = intel.prediction?.model_version ?? intel.explanation?.model_version;
  const analysisLoading = intel.loading.analysis;
  const profileLoading = intel.loading.profile && !intel.customer && !intel.error;

  return (
    <div className="space-y-5">
      <div>
        <nav className="mb-2 flex flex-wrap items-center gap-3 text-sm" aria-label="Page">
          <Link to="/" className="font-medium text-accent hover:underline">
            Back to Overview
          </Link>
          <span className="text-ink-faint" aria-hidden="true">
            ·
          </span>
          <Link to="/customers" className="font-medium text-accent hover:underline">
            Back to Customers
          </Link>
        </nav>
        <PageHeader
          eyebrow="Customer Intelligence"
          title={customerId}
          description="Predict, explain, recommend, simulate, then decide."
          actions={<Button onClick={intel.reload}>Refresh analysis</Button>}
        />
      </div>

      <WorkflowStrip compact />

      {intel.error ? <ErrorBanner message={intel.error} onRetry={intel.reload} /> : null}
      {profileLoading ? (
        <CustomerIntelligenceSkeleton />
      ) : null}

      {intel.customer ? (
        <>
          <section className="surface relative overflow-hidden px-5 py-5">
            <div
              className="pointer-events-none absolute -right-10 -top-16 h-40 w-40 rounded-full bg-accent/10 blur-3xl"
              aria-hidden="true"
            />
            <div className="relative grid gap-6 lg:grid-cols-[14rem_1fr]">
              <div className="rounded-panel border border-line bg-surface-muted/80 px-4 py-4">
                <p className="meta">Churn probability</p>
                <p className="mt-2 text-4xl font-semibold tabular-nums tracking-tight text-ink">
                  {formatPercent(probability)}
                </p>
                <p className="meta mt-4">Risk level</p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <RiskBadge level={risk} />
                </div>
                {version ? (
                  <p className="mt-4 text-xs text-ink-faint">Model version {version}</p>
                ) : null}
              </div>
              <div>
                <h2 className="section-title">Customer</h2>
                <dl className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {PROFILE_PRIMARY.map(([label, read]) => (
                    <div key={label}>
                      <dt className="text-xs text-ink-faint">{label}</dt>
                      <dd className="mt-0.5 text-sm font-medium text-ink">
                        {read(intel.customer) || "—"}
                      </dd>
                    </div>
                  ))}
                </dl>
                <button
                  type="button"
                  className="mt-4 text-sm font-medium text-accent hover:underline"
                  onClick={() => setShowFull((value) => !value)}
                >
                  {showFull ? "Hide full profile" : "View full profile"}
                </button>
                {showFull ? (
                  <dl className="mt-3 grid gap-3 border-t border-line pt-3 sm:grid-cols-2 lg:grid-cols-4">
                    {PROFILE_FULL.map(([label, read]) => (
                      <div key={label}>
                        <dt className="text-xs text-ink-faint">{label}</dt>
                        <dd className="mt-0.5 text-sm text-ink">
                          {read(intel.customer) || "—"}
                        </dd>
                      </div>
                    ))}
                  </dl>
                ) : null}
              </div>
            </div>
          </section>

          <div className="grid gap-4 xl:grid-cols-2">
            <SectionCard
              kicker="Predict"
              title="Churn prediction"
              description="This is the model's estimated probability of churn, not model accuracy."
              variant="model"
            >
              {intel.sectionErrors.prediction && probability == null ? (
                <p className="text-sm text-danger">{intel.sectionErrors.prediction}</p>
              ) : probability == null && analysisLoading ? (
                <p className="muted" role="status">
                  Loading churn prediction…
                </p>
              ) : probability == null ? (
                <p className="muted">No prediction is available for this customer yet.</p>
              ) : (
                <dl className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <dt className="meta">Churn probability</dt>
                    <dd className="mt-1 text-2xl font-semibold tabular-nums">
                      {formatPercent(probability)}
                    </dd>
                  </div>
                  <div>
                    <dt className="meta">Risk level</dt>
                    <dd className="mt-1">
                      <RiskBadge level={risk} />
                    </dd>
                  </div>
                </dl>
              )}
            </SectionCard>

            <SectionCard
              kicker="Explain"
              title="Top churn drivers"
              description="The strongest drivers that increased or decreased this customer's predicted churn risk."
              variant="shap"
            >
              {intel.sectionErrors.explanation && !intel.explanation ? (
                <p className="text-sm text-danger">{intel.sectionErrors.explanation}</p>
              ) : !intel.explanation && analysisLoading ? (
                <p className="muted" role="status">
                  Loading SHAP explanation…
                </p>
              ) : (
                <ShapBars drivers={intel.explanation?.top_drivers} />
              )}
            </SectionCard>
          </div>

          <SectionCard
            kicker="Recommend"
            title="Recommended retention action"
            description="AI-assisted decision support. A reviewer must approve any action."
            variant="ai"
          >
            <RecommendationPanel
              recommendation={intel.recommendation}
              loading={!intel.recommendation && analysisLoading}
              error={
                !intel.recommendation ? intel.sectionErrors.recommendation : null
              }
            />
          </SectionCard>

          <SectionCard
            kicker="Simulate"
            title="What-if analysis"
            description="Evaluate available interventions against the current predicted probability."
          >
            <WhatIfPanel
              result={intel.whatIf}
              loading={!intel.whatIf && analysisLoading}
              error={!intel.whatIf ? intel.sectionErrors.whatIf : null}
              selectedId={intel.selectedScenarioId}
              onSelect={intel.setSelectedScenarioId}
            />
          </SectionCard>

          <SectionCard
            kicker="Decide"
            title="Human decision"
            description="Approval records a reviewer's decision. It does not send a message or change the customer's plan."
            variant="decision"
          >
            {intel.sectionErrors.actions && !intel.currentAction ? (
              <p className="mb-3 text-sm text-danger">{intel.sectionErrors.actions}</p>
            ) : null}
            <DecisionPanel
              customerId={customerId}
              recommendation={intel.recommendation}
              probability={probability}
              currentAction={intel.currentAction}
              busy={intel.busy}
              onApprove={intel.approve}
              onModify={intel.modify}
              onReject={intel.reject}
              onNewReview={intel.newReview}
            />
          </SectionCard>
        </>
      ) : null}
    </div>
  );
}
