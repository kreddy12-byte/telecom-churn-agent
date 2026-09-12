import { useEffect, useState } from "react";
import PageHeader from "../components/common/PageHeader";
import ErrorBanner from "../components/common/ErrorBanner";
import SectionCard from "../components/common/SectionCard";
import { apiErrorMessage, getModelInfo } from "../services/api";

function Metric({ label, value }) {
  return (
    <div className="rounded-panel border border-line bg-surface-muted px-3.5 py-3 shadow-sm">
      <p className="meta">{label}</p>
      <p className="mt-1.5 text-lg font-semibold tabular-nums tracking-tight text-ink">{value}</p>
    </div>
  );
}

function asPercent(value) {
  return value == null ? "—" : `${(Number(value) * 100).toFixed(1)}%`;
}

export default function ModelInformation() {
  const [info, setInfo] = useState(null);
  const [error, setError] = useState(null);

  function load() {
    setError(null);
    getModelInfo()
      .then(setInfo)
      .catch((err) => setError(apiErrorMessage(err)));
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div>
      <PageHeader
        title="Model Intelligence"
        description="Facts from the locked training artifacts. Paths and secrets are not shown."
      />
      {error ? <ErrorBanner message={error} onRetry={load} /> : null}
      {!info && !error ? <p className="muted">Loading model metadata…</p> : null}
      {info ? (
        <div className="space-y-5">
          <SectionCard
            variant="model"
            kicker="Model"
            title="Locked model"
            description="The predictor used for every score, explanation, and what-if estimate."
          >
            <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <dt className="text-ink-faint">Algorithm</dt>
                <dd className="mt-0.5 font-medium">{info.model_name}</dd>
              </div>
              <div>
                <dt className="text-ink-faint">Version</dt>
                <dd className="mt-0.5 font-medium">{info.model_version}</dd>
              </div>
              <div>
                <dt className="text-ink-faint">Prediction objective</dt>
                <dd className="mt-0.5 font-medium">{info.target}</dd>
              </div>
              <div>
                <dt className="text-ink-faint">Explainability</dt>
                <dd className="mt-0.5 font-medium">{info.explainability}</dd>
              </div>
              <div>
                <dt className="text-ink-faint">Explained output</dt>
                <dd className="mt-0.5 font-medium">{info.explained_output}</dd>
              </div>
              <div>
                <dt className="text-ink-faint">Features</dt>
                <dd className="mt-0.5 font-medium">
                  {info.feature_count} original
                  {info.transformed_feature_count
                    ? ` · ${info.transformed_feature_count} transformed`
                    : ""}
                </dd>
              </div>
              <div>
                <dt className="text-ink-faint">Training dataset</dt>
                <dd className="mt-0.5 font-medium">
                  {info.dataset_name}
                  {info.dataset_rows_used ? ` · ${info.dataset_rows_used} rows` : ""}
                </dd>
              </div>
              <div>
                <dt className="text-ink-faint">Risk thresholds</dt>
                <dd className="mt-0.5 font-medium">
                  {info.risk_thresholds?.medium != null
                    ? `Medium ≥ ${info.risk_thresholds.medium}`
                    : "—"}
                  {info.risk_thresholds?.high != null
                    ? ` · High ≥ ${info.risk_thresholds.high}`
                    : ""}
                </dd>
              </div>
              {info.training_date ? (
                <div>
                  <dt className="text-ink-faint">Training date</dt>
                  <dd className="mt-0.5 font-medium">{info.training_date}</dd>
                </div>
              ) : null}
            </dl>
          </SectionCard>

          <SectionCard
            kicker="Evaluation"
            title="Held-out test metrics"
            description="Scores from the locked evaluation split. These are not live production KPIs."
          >
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
              <Metric label="Accuracy" value={asPercent(info.metrics?.accuracy)} />
              <Metric label="Precision" value={asPercent(info.metrics?.precision)} />
              <Metric label="Recall" value={asPercent(info.metrics?.recall)} />
              <Metric label="F1" value={asPercent(info.metrics?.f1)} />
              <Metric label="ROC AUC" value={asPercent(info.metrics?.roc_auc)} />
            </div>
            {info.metrics?.cv_recall_mean != null ? (
              <p className="mt-3 text-sm text-ink-muted">
                Cross-validation recall {asPercent(info.metrics.cv_recall_mean)}, F1{" "}
                {asPercent(info.metrics.cv_f1_mean)}, ROC AUC{" "}
                {asPercent(info.metrics.cv_roc_auc_mean)}.
              </p>
            ) : null}
          </SectionCard>

          {info.selection_reason ? (
            <SectionCard kicker="Selection" title="Why this model was selected" elevated>
              <p className="text-sm leading-6 text-ink">{info.selection_reason}</p>
            </SectionCard>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
