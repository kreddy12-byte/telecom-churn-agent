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

function sectionMessage(result, fallback) {
  if (result.status === "fulfilled") {
    return null;
  }
  return apiErrorMessage(result.reason) || fallback;
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

      const [predResult, explResult, recResult, whatIfResult, actionsResult] =
        await Promise.allSettled([
          predictCustomer(customerId),
          getExplanation(customerId, 5),
          getRecommendation(customerId, { detailed: true }),
          runWhatIf(customerId, { use_llm: false }),
          getActions({ customerId, limit: 20 }),
        ]);

      const nextErrors = {};

      if (predResult.status === "fulfilled") {
        setPrediction(predResult.value);
      } else if (!profile.latest_prediction) {
        nextErrors.prediction = sectionMessage(predResult, SECTION_ERRORS.prediction);
      }

      if (explResult.status === "fulfilled") {
        setExplanation(explResult.value);
      } else {
        nextErrors.explanation = sectionMessage(explResult, SECTION_ERRORS.explanation);
      }

      if (recResult.status === "fulfilled") {
        setRecommendation(recResult.value);
      } else {
        nextErrors.recommendation = sectionMessage(
          recResult,
          SECTION_ERRORS.recommendation
        );
      }

      if (whatIfResult.status === "fulfilled") {
        const simulation = whatIfResult.value;
        setWhatIf(simulation);
        setSelectedScenarioId(simulation.recommended_scenario_id);
      } else {
        nextErrors.whatIf = sectionMessage(whatIfResult, SECTION_ERRORS.whatIf);
      }

      if (actionsResult.status === "fulfilled") {
        setActions(actionsResult.value.items || []);
      } else {
        nextErrors.actions = sectionMessage(actionsResult, SECTION_ERRORS.actions);
      }

      setSectionErrors(nextErrors);
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
