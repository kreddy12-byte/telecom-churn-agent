import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Overview from "./Overview";
import {
  getGlobalImportance,
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
  getPredictionRanking: vi.fn(),
  getPredictionDistribution: vi.fn(),
  getGlobalImportance: vi.fn(),
  runBatchPredictions: vi.fn(),
}));

const OVERVIEW = {
  customer_count: 7043,
  evaluated_count: 12,
  risk_counts: { HIGH: 4, MEDIUM: 5, LOW: 3 },
  action_counts: { PENDING: 2, APPROVED: 1, MODIFIED: 0, REJECTED: 0 },
  recent_high_risk: [],
};

const SUMMARY = {
  total_scored: 12,
  risk_counts: { HIGH: 4, MEDIUM: 5, LOW: 3 },
  average_churn_probability: 0.4125,
  highest_churn_probability: 0.8064,
};

const FULL_SUMMARY = {
  total_scored: 7043,
  risk_counts: { HIGH: 2350, MEDIUM: 1718, LOW: 2975 },
  average_churn_probability: 0.4142,
  highest_churn_probability: 0.8064,
};

const RANKING = {
  items: [
    {
      customer_id: "0004-TLHLJ",
      churn_probability: 0.849,
      risk_level: "HIGH",
      contract: "Month-to-month",
      tenure: 4,
      monthly_charges: 73.9,
      model_version: "1.0.0",
      predicted_at: "2026-09-08T10:00:00Z",
    },
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
  meta: { total: 4, limit: 10, offset: 0 },
};

const DISTRIBUTION = {
  total_scored: 12,
  buckets: [
    { bucket: "0-10%", count: 1 },
    { bucket: "10-20%", count: 1 },
    { bucket: "20-30%", count: 1 },
    { bucket: "30-40%", count: 1 },
    { bucket: "40-50%", count: 2 },
    { bucket: "50-60%", count: 1 },
    { bucket: "60-70%", count: 1 },
    { bucket: "70-80%", count: 1 },
    { bucket: "80-90%", count: 2 },
    { bucket: "90-100%", count: 1 },
  ],
};

const DRIVERS = {
  explained_output: "log_odds",
  drivers: [
    { feature: "tenure", mean_absolute_shap: 1.022941, mean_signed_shap: -0.104327 },
    { feature: "InternetService", mean_absolute_shap: 0.593319, mean_signed_shap: -0.028382 },
    { feature: "MonthlyCharges", mean_absolute_shap: 0.588502, mean_signed_shap: 0.012705 },
    { feature: "Contract", mean_absolute_shap: 0.538909, mean_signed_shap: -0.089938 },
    { feature: "TotalCharges", mean_absolute_shap: 0.404246, mean_signed_shap: 0.032795 },
    { feature: "StreamingMovies", mean_absolute_shap: 0.23646, mean_signed_shap: -0.002133 },
    { feature: "StreamingTV", mean_absolute_shap: 0.226457, mean_signed_shap: -0.005458 },
    { feature: "OnlineSecurity", mean_absolute_shap: 0.191043, mean_signed_shap: -0.020108 },
  ],
};

function renderDashboard() {
  return render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route
          path="/customers/:customerId"
          element={<div>Intelligence for customer</div>}
        />
      </Routes>
    </MemoryRouter>
  );
}

describe("Churn Intelligence dashboard", () => {
  beforeEach(() => {
    getOverview.mockResolvedValue(OVERVIEW);
    getPredictionSummary.mockResolvedValue(SUMMARY);
    getPredictionRanking.mockResolvedValue(RANKING);
    getPredictionDistribution.mockResolvedValue(DISTRIBUTION);
    getGlobalImportance.mockResolvedValue(DRIVERS);
    runBatchPredictions.mockResolvedValue({
      processed: 7043,
      stored: 7043,
      model_version: "1.0.0",
      scored_at: "2026-09-09T08:00:00Z",
      risk_counts: { HIGH: 4, MEDIUM: 5, LOW: 3 },
    });
  });

  it("renders the dashboard title and summary cards", async () => {
    renderDashboard();
    expect(await screen.findByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect(
      screen.getByText(
        "Here are the customers most likely to churn, and here is where you investigate and decide what to do."
      )
    ).toBeInTheDocument();
    expect(screen.getByText("Total customers")).toBeInTheDocument();
    expect(screen.getByText("7,043")).toBeInTheDocument();
    expect(screen.getByText("Customers scored")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("High risk")).toBeInTheDocument();
    expect(
      within(screen.getByText("High risk").closest(".surface")).getByText("4")
    ).toBeInTheDocument();
    expect(screen.getByText("Medium risk")).toBeInTheDocument();
    expect(screen.getByText("Low risk")).toBeInTheDocument();
    expect(screen.getByText("Average churn probability")).toBeInTheDocument();
    expect(screen.getByText("41.25%")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Decision workflow" })).toBeInTheDocument();
  });

  it("renders the full scored population without inflating counts", async () => {
    getOverview.mockResolvedValue({ ...OVERVIEW, customer_count: 7043 });
    getPredictionSummary.mockResolvedValue(FULL_SUMMARY);

    renderDashboard();
    expect(await screen.findAllByText("2,350")).not.toHaveLength(0);
    expect(screen.getAllByText("1,718").length).toBeGreaterThan(0);
    expect(screen.getAllByText("2,975").length).toBeGreaterThan(0);
    expect(screen.getByText("41.42%")).toBeInTheDocument();
    expect(screen.getAllByText("33.4%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("24.4%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("42.2%").length).toBeGreaterThan(0);
    expect(
      screen.getByText(/not a certainty that the customer will churn/i)
    ).toBeInTheDocument();
  });

  it("renders customer risk distribution and the priority panel", async () => {
    renderDashboard();
    expect(
      await screen.findByRole("heading", { name: "Customer Risk Distribution" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Customer risk distribution donut chart" })
    ).toBeInTheDocument();
    expect(screen.getAllByText("HIGH RISK").length).toBeGreaterThan(0);
    expect(screen.getAllByText("MEDIUM RISK").length).toBeGreaterThan(0);
    expect(screen.getAllByText("LOW RISK").length).toBeGreaterThan(0);
    expect(
      screen.getByText(/High-risk customers are prioritized for deeper customer-level analysis/i)
    ).toBeInTheDocument();
  });

  it("renders the probability distribution histogram from stored scores", async () => {
    renderDashboard();
    expect(
      await screen.findByRole("heading", { name: "Churn Probability Distribution" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Churn probability distribution histogram" })
    ).toBeInTheDocument();
    expect(getPredictionDistribution).toHaveBeenCalled();
    expect(screen.queryByText("90-100% risk")).not.toBeInTheDocument();
  });

  it("shows high-risk ranking with percentage probability", async () => {
    renderDashboard();
    expect(await screen.findByText("7590-VHVEG")).toBeInTheDocument();
    expect(screen.getByText("80.64%")).toBeInTheDocument();
    expect(screen.getByText("0004-TLHLJ")).toBeInTheDocument();
    expect(screen.getByText("84.90%")).toBeInTheDocument();
    expect(screen.queryByText("1.0.0")).not.toBeInTheDocument();
    expect(screen.queryByText("0.8064")).not.toBeInTheDocument();
    expect(
      screen.getByText(/predicted likelihood of churn, not model accuracy or ROC-AUC/i)
    ).toBeInTheDocument();
    expect(getPredictionRanking).toHaveBeenCalledWith({
      risk: "HIGH",
      limit: 10,
      offset: 0,
    });
  });

  it("renders the top 10 high-risk customers as a priority queue", async () => {
    const items = Array.from({ length: 10 }, (_, index) => ({
      customer_id: `CUST-${String(index + 1).padStart(4, "0")}`,
      churn_probability: 0.95 - index * 0.01,
      risk_level: "HIGH",
      contract: "Month-to-month",
      tenure: index + 1,
      monthly_charges: 80 - index,
      model_version: "1.0.0",
      predicted_at: "2026-09-08T10:00:00Z",
    }));
    getPredictionRanking.mockResolvedValue({
      items,
      meta: { total: 10, limit: 10, offset: 0 },
    });

    renderDashboard();
    expect(
      await screen.findByRole("heading", { name: "Top High-Risk Customers" })
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Customers with the highest predicted churn probability. Open one to view intelligence and decide what to do."
      )
    ).toBeInTheDocument();
    expect(screen.getByText("CUST-0001")).toBeInTheDocument();
    expect(screen.getByText("CUST-0010")).toBeInTheDocument();
    expect(screen.getByText("95.00%")).toBeInTheDocument();
    expect(screen.getByText("86.00%")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /View intelligence/ })).toHaveLength(10);
    expect(screen.getAllByText("HIGH risk").length).toBeGreaterThan(0);
  });

  it("renders stored global churn drivers with readable labels", async () => {
    renderDashboard();
    const driversHeading = await screen.findByRole("heading", {
      name: "Top Churn Drivers",
    });
    const driversSection = driversHeading.closest("section");
    expect(within(driversSection).getByText("Tenure")).toBeInTheDocument();
    expect(within(driversSection).getByText("Internet Service")).toBeInTheDocument();
    expect(within(driversSection).getByText("Monthly Charges")).toBeInTheDocument();
    expect(within(driversSection).getByText("Contract Type")).toBeInTheDocument();
    expect(
      screen.getByText(/do not imply causation/i)
    ).toBeInTheDocument();
    expect(getGlobalImportance).toHaveBeenCalledWith(8);
  });

  it("shows an empty prediction state without fake risk zeros", async () => {
    getPredictionSummary.mockResolvedValue({
      total_scored: 0,
      risk_counts: { HIGH: 0, MEDIUM: 0, LOW: 0 },
      average_churn_probability: null,
      highest_churn_probability: null,
    });
    getPredictionRanking.mockResolvedValue({
      items: [],
      meta: { total: 0, limit: 10, offset: 0 },
    });
    getPredictionDistribution.mockResolvedValue({
      total_scored: 0,
      buckets: DISTRIBUTION.buckets.map((row) => ({ ...row, count: 0 })),
    });

    renderDashboard();
    expect(
      await screen.findByText("Prediction data is not available yet.")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Run batch prediction to populate the dashboard.")
    ).toBeInTheDocument();
    expect(screen.getByText("Total customers")).toBeInTheDocument();
    expect(screen.queryByText("High risk")).not.toBeInTheDocument();
    expect(screen.queryByText("Average churn probability")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Retention Priority" })).toBeInTheDocument();
  });

  it("shows a single loading message before data arrives", async () => {
    let resolveSummary;
    getPredictionSummary.mockReturnValue(
      new Promise((resolve) => {
        resolveSummary = resolve;
      })
    );

    renderDashboard();
    expect(screen.getByText("Loading churn intelligence...")).toBeInTheDocument();
    expect(screen.queryAllByText("Loading churn intelligence...")).toHaveLength(1);

    resolveSummary(SUMMARY);
    expect(await screen.findByText("7,043")).toBeInTheDocument();
    expect(screen.queryByText("Loading churn intelligence...")).not.toBeInTheDocument();
  });

  it("shows a useful error when prediction summary is missing", async () => {
    getPredictionSummary.mockRejectedValue({
      response: { status: 404, data: { error: { code: "not_found" } } },
    });

    renderDashboard();
    expect(
      await screen.findByText("Unable to load churn intelligence.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("shows a friendly error and retry when the API fails", async () => {
    getPredictionSummary.mockRejectedValue(new Error("ECONNREFUSED internals"));

    renderDashboard();
    expect(
      await screen.findByText("Unable to load churn intelligence.")
    ).toBeInTheDocument();
    expect(screen.queryByText(/ECONNREFUSED/)).not.toBeInTheDocument();

    getPredictionSummary.mockResolvedValue(SUMMARY);
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("7,043")).toBeInTheDocument();
  });

  it("keeps the dashboard usable when ranking is unavailable", async () => {
    getPredictionRanking.mockRejectedValue(new Error("ranking down"));

    renderDashboard();
    expect(await screen.findByText("High risk")).toBeInTheDocument();
    expect(
      await screen.findByText(
        "High-risk ranking is not available. Open the customer list to continue review."
      )
    ).toBeInTheDocument();
    expect(screen.getByText("41.25%")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Top Churn Drivers" })).toBeInTheDocument();
  });

  it("keeps the dashboard usable when the probability histogram is unavailable", async () => {
    getPredictionDistribution.mockRejectedValue(new Error("distribution down"));

    renderDashboard();
    expect(await screen.findByText("High risk")).toBeInTheDocument();
    expect(
      await screen.findByText(
        "Churn probability distribution is not available. The rest of the dashboard is still usable."
      )
    ).toBeInTheDocument();
    expect(screen.getByText("7590-VHVEG")).toBeInTheDocument();
  });

  it("keeps the dashboard usable when global SHAP importance is unavailable", async () => {
    getGlobalImportance.mockRejectedValue(new Error("shap artifact missing"));

    renderDashboard();
    expect(await screen.findByText("High risk")).toBeInTheDocument();
    expect(
      await screen.findByText(
        "Global SHAP importance is not available. Customer-level explanations still work from the intelligence page."
      )
    ).toBeInTheDocument();
    expect(screen.getByText("7590-VHVEG")).toBeInTheDocument();
  });

  it("does not run batch prediction on mount", async () => {
    renderDashboard();
    expect(await screen.findByText("7,043")).toBeInTheDocument();
    expect(runBatchPredictions).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: "Run Batch Prediction" })
    ).toBeInTheDocument();
  });

  it("disables the batch button while scoring and refreshes afterwards", async () => {
    let finishBatch;
    runBatchPredictions.mockReturnValue(
      new Promise((resolve) => {
        finishBatch = resolve;
      })
    );
    const refreshedSummary = {
      ...SUMMARY,
      total_scored: 7043,
      risk_counts: { HIGH: 10, MEDIUM: 20, LOW: 7013 },
    };
    getPredictionSummary.mockImplementation(() => Promise.resolve(SUMMARY));

    renderDashboard();
    const button = await screen.findByRole("button", {
      name: "Run Batch Prediction",
    });

    await userEvent.click(button);
    await userEvent.click(button);
    expect(runBatchPredictions).toHaveBeenCalledTimes(1);
    expect(
      screen.getByRole("button", { name: "Scoring customer base..." })
    ).toBeDisabled();

    const callsBeforeRefresh = getPredictionSummary.mock.calls.length;
    getPredictionSummary.mockImplementation(() => Promise.resolve(refreshedSummary));

    finishBatch({
      processed: 7043,
      stored: 7043,
      model_version: "1.0.0",
      scored_at: "2026-09-09T08:00:00Z",
      risk_counts: { HIGH: 10, MEDIUM: 20, LOW: 7013 },
    });

    expect(
      await screen.findByText("Scored 7,043 customers. Priority list updated.")
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(getPredictionSummary.mock.calls.length).toBeGreaterThan(callsBeforeRefresh);
      expect(getPredictionRanking.mock.calls.length).toBeGreaterThan(1);
    });
    expect(screen.getByText("High risk")).toBeInTheDocument();
    expect(
      within(screen.getByText("High risk").closest(".surface")).getByText("10")
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Run Batch Prediction" })
    ).toBeEnabled();
  });

  it("shows a useful message when batch prediction fails", async () => {
    runBatchPredictions.mockRejectedValue(new Error("batch timeout internals"));

    renderDashboard();
    await userEvent.click(
      await screen.findByRole("button", { name: "Run Batch Prediction" })
    );
    expect(
      await screen.findByText("Unable to score the customer base. Please try again.")
    ).toBeInTheDocument();
    expect(screen.queryByText(/batch timeout internals/)).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Run Batch Prediction" })
    ).toBeEnabled();
    expect(screen.getByText("7,043")).toBeInTheDocument();
  });

  it("navigates from a ranked customer to the intelligence page", async () => {
    renderDashboard();
    const link = await screen.findByRole("link", { name: "7590-VHVEG" });
    expect(link).toHaveAttribute("href", "/customers/7590-VHVEG");
    await userEvent.click(link);
    expect(screen.getByText("Intelligence for customer")).toBeInTheDocument();
  });

  it("navigates from the view-intelligence action", async () => {
    renderDashboard();
    const action = await screen.findByRole("link", {
      name: "View intelligence for 7590-VHVEG",
    });
    expect(action).toHaveAttribute("href", "/customers/7590-VHVEG");
    await userEvent.click(action);
    expect(screen.getByText("Intelligence for customer")).toBeInTheDocument();
  });

  it("links to the existing customers views", async () => {
    renderDashboard();
    expect(await screen.findByText("View all customers")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View all customers" })).toHaveAttribute(
      "href",
      "/customers"
    );
    expect(
      screen.getByRole("link", { name: "View high-risk customers" })
    ).toHaveAttribute("href", "/customers?risk_level=HIGH");
  });

  it("keeps the priority table in a horizontally scrollable container", async () => {
    renderDashboard();
    const customer = await screen.findByText("7590-VHVEG");
    const scroller = customer.closest(".overflow-x-auto");
    expect(scroller).toBeTruthy();
    expect(within(scroller).getByText("Churn probability")).toBeInTheDocument();
    expect(within(scroller).getByText("Contract")).toBeInTheDocument();
    expect(within(scroller).getByText("Tenure")).toBeInTheDocument();
    expect(within(scroller).getByText("Monthly charges")).toBeInTheDocument();
  });

  it("explains the identify / understand / act retention workflow", async () => {
    renderDashboard();
    expect(
      await screen.findByRole("heading", { name: "Retention Priority" })
    ).toBeInTheDocument();
    expect(screen.getByText("Identify")).toBeInTheDocument();
    expect(screen.getByText("Understand")).toBeInTheDocument();
    expect(screen.getByText("Act")).toBeInTheDocument();
  });
});
