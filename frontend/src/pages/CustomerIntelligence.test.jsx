import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CustomerIntelligence from "./CustomerIntelligence";

function makeIntel() {
  return {
    customer: {
      customer_id: "7590-VHVEG",
      tenure: 1,
      contract: "Month-to-month",
      internet_service: "DSL",
      monthly_charges: 29.85,
      total_charges: 29.85,
      payment_method: "Electronic check",
      tech_support: "No",
      online_security: "No",
    },
    prediction: {
      churn_probability: 0.8064,
      risk_level: "HIGH",
      model_version: "1.0.0",
    },
    explanation: {
      churn_probability: 0.8064,
      risk_level: "HIGH",
      model_version: "1.0.0",
      explained_output: "log_odds",
      base_value: -1.2,
      top_drivers: [
        { feature: "tenure", shap_value: 1.3752, direction: "increases_risk", value: 1 },
        { feature: "MonthlyCharges", shap_value: 0.7998, direction: "increases_risk", value: 29.85 },
        { feature: "InternetService", shap_value: -0.6895, direction: "decreases_risk", value: "DSL" },
      ],
    },
    recommendation: {
      selected_strategy: {
        strategy_id: "EARLY_LIFECYCLE_ONBOARDING",
        strategy_name: "Early Lifecycle Onboarding",
      },
      recommendation: "Arrange a personalised onboarding review.",
      reasoning: ["Short tenure is the strongest risk-increasing driver."],
      supporting_evidence: [
        { feature: "tenure", value: 1, shap_value: 1.3752, direction: "increases_risk" },
      ],
      priority: "HIGH",
      confidence: "MEDIUM",
      requires_human_approval: true,
      provider: "deterministic_fallback",
      fallback_reason: "No LLM provider is configured; used the deterministic strategy engine.",
    },
    whatIf: {
      baseline: { churn_probability: 0.8064, risk_level: "HIGH" },
      recommended_scenario_id: "two_year_contract",
      selection_reason: "Largest model-estimate reduction among ranked scenarios.",
      scenarios: [
        {
          scenario_id: "two_year_contract",
          scenario_name: "Move to Two-Year Contract",
          scenario_probability: 0.4984,
          absolute_probability_change: -0.308,
          baseline_risk_level: "HIGH",
          scenario_risk_level: "MEDIUM",
          ranking_score: 0.9,
          ranking_factors: {},
          changed_features: { Contract: "Two year" },
          description: "Contract becomes two year.",
          model_based_interpretation: "The contract contribution reverses.",
          driver_deltas: [],
        },
      ],
    },
    currentAction: null,
    selectedScenarioId: "two_year_contract",
    setSelectedScenarioId: vi.fn(),
    sectionErrors: {},
    loading: { profile: false, analysis: false },
    error: null,
    busy: false,
    reload: vi.fn(),
    approve: vi.fn(),
    modify: vi.fn(),
    reject: vi.fn(),
    newReview: vi.fn(),
  };
}

const INTEL = makeIntel();

vi.mock("../hooks/useCustomerIntelligence", () => ({
  useCustomerIntelligence: () => INTEL,
}));

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/customers/7590-VHVEG"]}>
      <Routes>
        <Route path="/customers/:customerId" element={<CustomerIntelligence />} />
        <Route path="/" element={<div>Overview page</div>} />
        <Route path="/customers" element={<div>Customers page</div>} />
        <Route path="/actions" element={<div>Retention actions page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("CustomerIntelligence", () => {
  beforeEach(() => {
    Object.assign(INTEL, makeIntel());
  });

  it("renders the decision workflow from API-backed intelligence", () => {
    renderPage();

    expect(screen.getAllByText("7590-VHVEG").length).toBeGreaterThan(0);
    expect(screen.getAllByText("80.64%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("HIGH risk").length).toBeGreaterThan(0);
    expect(screen.getByText("Top churn drivers")).toBeInTheDocument();
    expect(screen.getByText("+1.3752")).toBeInTheDocument();
    expect(screen.getByText("Early Lifecycle Onboarding")).toBeInTheDocument();
    expect(screen.getByText(/Human approval required/i)).toBeInTheDocument();
    expect(screen.getAllByText("Move to Two-Year Contract").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
  });

  it("shows prediction language without confusing probability with accuracy", () => {
    renderPage();
    expect(
      screen.getByText("This is the model's estimated probability of churn, not model accuracy.")
    ).toBeInTheDocument();
    expect(screen.getByText("Churn prediction")).toBeInTheDocument();
    expect(screen.queryByText(/ROC-AUC/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/model accuracy or ROC-AUC/i)).not.toBeInTheDocument();
  });

  it("hides SHAP internals and uses business feature labels", () => {
    renderPage();
    expect(screen.getAllByText("Monthly Charges").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Internet Service").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Increases churn risk").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Decreases churn risk").length).toBeGreaterThan(0);
    expect(screen.queryByText(/log_odds/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Explained output/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Base value/i)).not.toBeInTheDocument();
  });

  it("identifies deterministic fallback reasoning without looking broken", () => {
    renderPage();
    expect(screen.getByText("System-generated fallback reasoning")).toBeInTheDocument();
    expect(screen.getByText("Why this action was selected")).toBeInTheDocument();
    expect(screen.queryByText(/SHAP 1.3752/)).not.toBeInTheDocument();
  });

  it("shows what-if current, hypothetical, and percentage-point change", () => {
    renderPage();
    expect(screen.getAllByText("49.84%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("-30.80 pp").length).toBeGreaterThan(0);
    expect(
      screen.getByText("Model-based what-if estimate — not a causal prediction.")
    ).toBeInTheDocument();
    expect(screen.queryByText("0.9")).not.toBeInTheDocument();
  });

  it("keeps the page usable when SHAP fails", () => {
    INTEL.explanation = null;
    INTEL.sectionErrors = { explanation: "Unable to load the SHAP explanation." };
    renderPage();
    expect(screen.getByText("Unable to load the SHAP explanation.")).toBeInTheDocument();
    expect(screen.getAllByText("80.64%").length).toBeGreaterThan(0);
    expect(screen.getByText("Early Lifecycle Onboarding")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
  });

  it("shows per-section loading without a duplicate page-level message", () => {
    INTEL.explanation = null;
    INTEL.recommendation = null;
    INTEL.whatIf = null;
    INTEL.loading = { profile: false, analysis: true };
    renderPage();
    expect(screen.getByText("Loading SHAP explanation…")).toBeInTheDocument();
    expect(screen.getByText("Loading retention recommendation…")).toBeInTheDocument();
    expect(screen.getByText("Loading what-if scenarios…")).toBeInTheDocument();
    expect(screen.queryByText("Loading customer…")).not.toBeInTheDocument();
    expect(screen.queryByText("Waiting for the explanation…")).not.toBeInTheDocument();
  });

  it("links back to Overview and Customers", () => {
    renderPage();
    expect(screen.getByRole("link", { name: "Back to Overview" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Back to Customers" })).toHaveAttribute(
      "href",
      "/customers"
    );
  });

  it("confirms an approved action and links to retention actions", async () => {
    INTEL.currentAction = {
      id: 12,
      customer_id: "7590-VHVEG",
      strategy_id: "EARLY_LIFECYCLE_ONBOARDING",
      status: "APPROVED",
      reviewed_by_name: "Ada Reviewer",
      reviewed_by_email: "ada@example.test",
      updated_at: "2026-09-09T10:00:00Z",
    };
    renderPage();
    expect(screen.getByText("Retention action approved")).toBeInTheDocument();
    expect(screen.getByText("Ada Reviewer")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    const actionsLink = screen.getByRole("link", { name: "View retention actions" });
    expect(actionsLink).toHaveAttribute("href", "/actions");
    await userEvent.click(actionsLink);
    expect(screen.getByText("Retention actions page")).toBeInTheDocument();
  });
});
