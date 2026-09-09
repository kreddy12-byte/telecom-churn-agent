import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useCustomerIntelligence } from "./useCustomerIntelligence";
import {
  getActions,
  getCustomer,
  getExplanation,
  getRecommendation,
  predictCustomer,
  runWhatIf,
} from "../services/api";

vi.mock("../services/api", () => ({
  apiErrorMessage: (err) => err.message || "Unable to load.",
  getCustomer: vi.fn(),
  predictCustomer: vi.fn(),
  getExplanation: vi.fn(),
  getRecommendation: vi.fn(),
  runWhatIf: vi.fn(),
  getActions: vi.fn(),
  createAction: vi.fn(),
  updateAction: vi.fn(),
}));

const PROFILE = {
  customer_id: "7590-VHVEG",
  tenure: 1,
  latest_prediction: {
    churn_probability: 0.8064,
    risk_level: "HIGH",
    model_version: "1.0.0",
  },
};

const PREDICTION = {
  customer_id: "7590-VHVEG",
  churn_probability: 0.8064,
  risk_level: "HIGH",
  model_version: "1.0.0",
};

const EXPLANATION = { top_drivers: [{ feature: "tenure", shap_value: 1.3752 }] };
const RECOMMENDATION = {
  selected_strategy: { strategy_id: "EARLY_LIFECYCLE_ONBOARDING" },
  recommendation: "Onboard the customer.",
  provider: "deterministic_fallback",
};
const WHAT_IF = {
  recommended_scenario_id: "two_year_contract",
  scenarios: [],
};

describe("useCustomerIntelligence", () => {
  beforeEach(() => {
    getCustomer.mockResolvedValue(PROFILE);
    predictCustomer.mockResolvedValue(PREDICTION);
    getExplanation.mockResolvedValue(EXPLANATION);
    getRecommendation.mockResolvedValue(RECOMMENDATION);
    runWhatIf.mockResolvedValue(WHAT_IF);
    getActions.mockResolvedValue({ items: [] });
  });

  it("loads customer intelligence without duplicate requests", async () => {
    const { result } = renderHook(() => useCustomerIntelligence("7590-VHVEG"));
    await waitFor(() => {
      expect(result.current.customer?.customer_id).toBe("7590-VHVEG");
      expect(result.current.prediction?.churn_probability).toBe(0.8064);
      expect(result.current.explanation).toEqual(EXPLANATION);
      expect(result.current.recommendation).toEqual(RECOMMENDATION);
      expect(result.current.whatIf).toEqual(WHAT_IF);
    });
    expect(getCustomer).toHaveBeenCalledTimes(1);
    expect(predictCustomer).toHaveBeenCalledTimes(1);
    expect(getExplanation).toHaveBeenCalledTimes(1);
    expect(getRecommendation).toHaveBeenCalledTimes(1);
    expect(runWhatIf).toHaveBeenCalledTimes(1);
    expect(getActions).toHaveBeenCalledTimes(1);
  });

  it("keeps prediction, recommendation, and what-if when SHAP fails", async () => {
    getExplanation.mockRejectedValue(new Error("shap unavailable"));
    const { result } = renderHook(() => useCustomerIntelligence("7590-VHVEG"));
    await waitFor(() => {
      expect(result.current.customer?.customer_id).toBe("7590-VHVEG");
      expect(result.current.prediction?.churn_probability).toBe(0.8064);
      expect(result.current.recommendation).toEqual(RECOMMENDATION);
      expect(result.current.whatIf).toEqual(WHAT_IF);
      expect(result.current.explanation).toBeNull();
      expect(result.current.sectionErrors.explanation).toMatch(/shap unavailable/i);
      expect(result.current.error).toBeNull();
    });
  });
});
