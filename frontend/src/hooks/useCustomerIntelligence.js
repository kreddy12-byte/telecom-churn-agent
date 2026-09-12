import { useCallback, useEffect, useState } from "react";
import {
  apiErrorMessage,
  createAction,
  getActions,
  getCustomer,
  getExplanation,
  getRecommendation,
  predictCustomer,
  runWhatIf,
  updateAction,
} from "../services/api";

const SECTION_ERRORS = {
  prediction: "Unable to load the churn prediction.",
  explanation: "Unable to load the SHAP explanation.",
  recommendation: "Unable to load the retention recommendation.",
  whatIf: "Unable to load what-if scenarios.",
  actions: "Unable to load the current retention action.",
};

function sectionMessage(reason, fallback) {
  return apiErrorMessage(reason) || fallback;
}

export function useCustomerIntelligence(customerId) {
  const [customer, setCustomer] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [explanation, setExplanation] = useState(null);
  const [recommendation, setRecommendation] = useState(null);
  const [whatIf, setWhatIf] = useState(null);
  const [actions, setActions] = useState([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState(null);
  const [sectionErrors, setSectionErrors] = useState({});
  const [loading, setLoading] = useState({
    profile: true,
    analysis: false,
  });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    setSectionErrors({});
    setCustomer(null);
    setPrediction(null);
    setExplanation(null);
    setRecommendation(null);
    setWhatIf(null);
    setActions([]);
    setSelectedScenarioId(null);
    setLoading({ profile: true, analysis: false });

    try {
      const profile = await getCustomer(customerId);
      setCustomer(profile);
      if (profile.latest_prediction) {
        setPrediction({
          customer_id: profile.customer_id,
          ...profile.latest_prediction,
        });
      }
      setLoading({ profile: false, analysis: true });

      // Progressive: each section paints as soon as its request settles.
      // Analysis loading clears only after every independent request finishes.
      const nextErrors = {};

      const predictionTask = predictCustomer(customerId).then(
        (value) => {
          setPrediction(value);
        },
        (reason) => {
          if (!profile.latest_prediction) {
            nextErrors.prediction = sectionMessage(reason, SECTION_ERRORS.prediction);
          }
        }
      );

      const explanationTask = getExplanation(customerId, 5).then(
        (value) => {
          setExplanation(value);
        },
        (reason) => {
          nextErrors.explanation = sectionMessage(reason, SECTION_ERRORS.explanation);
        }
      );

      const recommendationTask = getRecommendation(customerId, { detailed: true }).then(
        (value) => {
          setRecommendation(value);
        },
        (reason) => {
          nextErrors.recommendation = sectionMessage(
            reason,
            SECTION_ERRORS.recommendation
          );
        }
      );

      const whatIfTask = runWhatIf(customerId, { use_llm: false }).then(
        (simulation) => {
          setWhatIf(simulation);
          setSelectedScenarioId(simulation.recommended_scenario_id);
        },
        (reason) => {
          nextErrors.whatIf = sectionMessage(reason, SECTION_ERRORS.whatIf);
        }
      );

      const actionsTask = getActions({ customerId, limit: 20 }).then(
        (actionPage) => {
          setActions(actionPage.items || []);
        },
        (reason) => {
          nextErrors.actions = sectionMessage(reason, SECTION_ERRORS.actions);
        }
      );

      await Promise.all([
        predictionTask,
        explanationTask,
        recommendationTask,
        whatIfTask,
        actionsTask,
      ]);
      setSectionErrors({ ...nextErrors });
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading({ profile: false, analysis: false });
    }
  }, [customerId]);

  useEffect(() => {
    load();
  }, [load]);

  const currentAction = actions[0] || null;

  async function ensurePending(payload) {
    if (currentAction?.status === "PENDING" || currentAction?.status === "MODIFIED") {
      return currentAction;
    }
    const created = await createAction({
      customer_id: customerId,
      strategy_id: payload.strategy_id,
      recommendation: payload.recommendation,
      reviewer_note: payload.reviewer_note || null,
    });
    return created;
  }

  async function refreshActions() {
    const actionPage = await getActions({ customerId, limit: 20 });
    setActions(actionPage.items || []);
  }

  async function approve() {
    setBusy(true);
    try {
      const pending = await ensurePending({
        strategy_id:
          recommendation?.selected_strategy?.strategy_id || "GENERAL_RETENTION_REVIEW",
        recommendation:
          recommendation?.recommendation || "Human review of model output.",
      });
      await updateAction(pending.id, { status: "APPROVED" });
      await refreshActions();
    } catch (err) {
      setError(apiErrorMessage(err));
      throw err;
    } finally {
      setBusy(false);
    }
  }

  async function modify({ strategyId, recommendation: text, reviewerNote }) {
    setBusy(true);
    try {
      const pending = await ensurePending({
        strategy_id: strategyId,
        recommendation: text,
        reviewer_note: reviewerNote,
      });
      await updateAction(pending.id, {
        status: "MODIFIED",
        reviewer_note: reviewerNote,
        recommendation: text,
      });
      await refreshActions();
    } catch (err) {
      setError(apiErrorMessage(err));
      throw err;
    } finally {
      setBusy(false);
    }
  }

  async function reject(reviewerNote) {
    setBusy(true);
    try {
      const pending = await ensurePending({
        strategy_id:
          recommendation?.selected_strategy?.strategy_id || "GENERAL_RETENTION_REVIEW",
        recommendation:
          recommendation?.recommendation || "Human review of model output.",
        reviewer_note: reviewerNote,
      });
      await updateAction(pending.id, {
        status: "REJECTED",
        reviewer_note: reviewerNote,
      });
      await refreshActions();
    } catch (err) {
      setError(apiErrorMessage(err));
      throw err;
    } finally {
      setBusy(false);
    }
  }

  async function newReview() {
    setBusy(true);
    try {
      await createAction({
        customer_id: customerId,
        strategy_id:
          recommendation?.selected_strategy?.strategy_id || "GENERAL_RETENTION_REVIEW",
        recommendation:
          recommendation?.recommendation || "Human review of model output.",
      });
      await refreshActions();
    } finally {
      setBusy(false);
    }
  }

  return {
    customer,
    prediction,
    explanation,
    recommendation,
    whatIf,
    actions,
    currentAction,
    selectedScenarioId,
    setSelectedScenarioId,
    sectionErrors,
    loading,
    error,
    busy,
    reload: load,
    approve,
    modify,
    reject,
    newReview,
  };
}
