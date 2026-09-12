import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import BatchAnalysis from "./BatchAnalysis";
import {
  getModelInfo,
  getOverview,
  getPredictionDistribution,
  getPredictionRanking,
  getPredictionSummary,
  runBatchPredictions,
} from "../services/api";

vi.mock("../services/api", () => ({
  apiErrorMessage: (err) => err.message || "Unable to load.",
  getOverview: vi.fn(),
  getPredictionSummary: vi.fn(),
  getPredictionDistribution: vi.fn(),
  getPredictionRanking: vi.fn(),
  getModelInfo: vi.fn(),
  runBatchPredictions: vi.fn(),
}));

const OVERVIEW = {
  customer_count: 7043,
  evaluated_count: 12,
  risk_counts: { HIGH: 4, MEDIUM: 5, LOW: 3 },
  action_counts: { PENDING: 0, APPROVED: 0, MODIFIED: 0, REJECTED: 0 },
};

const EMPTY_SUMMARY = {
  total_scored: 0,
  risk_counts: { HIGH: 0, MEDIUM: 0, LOW: 0 },
  average_churn_probability: null,
  highest_churn_probability: null,
};

const SUMMARY = {
  total_scored: 7043,
  risk_counts: { HIGH: 2350, MEDIUM: 1718, LOW: 2975 },
  average_churn_probability: 0.4142,
  highest_churn_probability: 0.849,
};

const DISTRIBUTION = {
  total_scored: 7043,
  buckets: [
    { bucket: "0-10%", count: 400 },
    { bucket: "80-90%", count: 500 },
  ],
};

const RANKING = {
  items: [
    {
      customer_id: "7590-VHVEG",
      churn_probability: 0.8064,
      risk_level: "HIGH",
      contract: "Month-to-month",
      tenure: 1,
      monthly_charges: 29.85,
      model_version: "1.0.0",
      predicted_at: "2026-09-08T10:00:00Z",
    },
  ],
  meta: { total: 1, limit: 10, offset: 0 },
};

const MODEL = {
  model_name: "Logistic Regression",
  model_version: "1.0.0",
  target: "churn",
  explainability: "SHAP",
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/batch"]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/batch" element={<BatchAnalysis />} />
        <Route path="/customers/:customerId" element={<div>Intelligence for customer</div>} />
        <Route path="/customers" element={<div>Customers list</div>} />
        <Route path="/model" element={<div>Model page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("Batch Analysis", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getOverview.mockResolvedValue(OVERVIEW);
    getPredictionSummary.mockResolvedValue(EMPTY_SUMMARY);
    getPredictionDistribution.mockResolvedValue({ total_scored: 0, buckets: [] });
    getPredictionRanking.mockResolvedValue({ items: [], meta: { total: 0, limit: 10, offset: 0 } });
    getModelInfo.mockResolvedValue(MODEL);
    runBatchPredictions.mockResolvedValue({
      processed: 7043,
      stored: 7043,
      model_version: "1.0.0",
      scored_at: "2026-09-10T12:00:00Z",
      risk_counts: { HIGH: 2350, MEDIUM: 1718, LOW: 2975 },
    });
  });

  it("renders the ready workspace for the connected customer population", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "Batch Analysis" })).toBeInTheDocument();
    expect(screen.getByText("7,043")).toBeInTheDocument();
    expect(screen.getByText("Connected customer database")).toBeInTheDocument();
    expect(screen.getByText("Ready for analysis")).toBeInTheDocument();
    expect(screen.getByText("CSV upload not supported yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload dataset (unavailable)" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Run Batch Analysis" })).toBeEnabled();
    expect(screen.getByText("No batch analysis yet")).toBeInTheDocument();
    expect(runBatchPredictions).not.toHaveBeenCalled();
  });

  it("runs batch analysis and reveals results from existing APIs", async () => {
    getPredictionSummary
      .mockResolvedValueOnce(EMPTY_SUMMARY)
      .mockResolvedValue(SUMMARY);
    getPredictionDistribution
      .mockResolvedValueOnce({ total_scored: 0, buckets: [] })
      .mockResolvedValue(DISTRIBUTION);
    getPredictionRanking
      .mockResolvedValueOnce({ items: [], meta: { total: 0, limit: 10, offset: 0 } })
      .mockResolvedValue(RANKING);

    renderPage();
    await screen.findByRole("button", { name: "Run Batch Analysis" });
    await userEvent.click(screen.getByRole("button", { name: "Run Batch Analysis" }));

    await waitFor(() => {
      expect(runBatchPredictions).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByText("Total analyzed")).toBeInTheDocument();
    expect(screen.getByText("41.42%")).toBeInTheDocument();
    expect(screen.getByText("7590-VHVEG")).toBeInTheDocument();
    expect(screen.getByText(/Analysis completed/i)).toBeInTheDocument();
    expect(screen.getByText("Logistic Regression")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run Batch Analysis" })).toBeEnabled();
  });

  it("shows a useful error when batch analysis fails", async () => {
    runBatchPredictions.mockRejectedValue(new Error("batch timeout internals"));
    renderPage();
    await screen.findByRole("button", { name: "Run Batch Analysis" });
    await userEvent.click(screen.getByRole("button", { name: "Run Batch Analysis" }));
    expect(await screen.findByText("batch timeout internals")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("shows a load failure with retry", async () => {
    getOverview.mockRejectedValue(new Error("workspace unavailable"));
    renderPage();
    expect(await screen.findByText("workspace unavailable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("navigates from a ranked customer to customer intelligence", async () => {
    getPredictionSummary.mockResolvedValue(SUMMARY);
    getPredictionDistribution.mockResolvedValue(DISTRIBUTION);
    getPredictionRanking.mockResolvedValue(RANKING);
    renderPage();
    const link = await screen.findByRole("link", { name: /View intelligence for 7590-VHVEG/i });
    expect(link).toHaveAttribute("href", "/customers/7590-VHVEG");
    await userEvent.click(link);
    expect(screen.getByText("Intelligence for customer")).toBeInTheDocument();
  });
});
