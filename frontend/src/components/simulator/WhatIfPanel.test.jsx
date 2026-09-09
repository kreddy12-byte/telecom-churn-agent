import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import WhatIfPanel from "./WhatIfPanel";

const RESULT = {
  baseline: { churn_probability: 0.8064, risk_level: "HIGH" },
  recommended_scenario_id: "two_year_contract",
  selection_reason: "Highest ranking score.",
  scenarios: [
    {
      scenario_id: "two_year_contract",
      scenario_name: "Move to Two-Year Contract",
      description: "Hypothetically change the contract.",
      changed_features: { Contract: "Two year" },
      scenario_probability: 0.4984,
      absolute_probability_change: -0.308,
      baseline_risk_level: "HIGH",
      scenario_risk_level: "MEDIUM",
      ranking_score: 0.232,
      ranking_factors: {
        model_response: 0.38,
        evidence_alignment: 0.08,
        driver_targeting: 0.08,
      },
      model_based_interpretation: "The trained model estimates a lower probability.",
      driver_deltas: [
        {
          feature: "Contract",
          baseline_shap: 0.4077,
          scenario_shap: -1.0255,
          shap_change: -1.4332,
          changed_by_scenario: true,
        },
      ],
    },
    {
      scenario_id: "annual_contract",
      scenario_name: "Move to One-Year Contract",
      description: "One-year profile.",
      changed_features: { Contract: "One year" },
      scenario_probability: 0.6675,
      absolute_probability_change: -0.1389,
      baseline_risk_level: "HIGH",
      scenario_risk_level: "HIGH",
      ranking_score: 0.12,
      ranking_factors: {
        model_response: 0.17,
        evidence_alignment: 0.08,
        driver_targeting: 0.08,
      },
      model_based_interpretation: "The trained model estimates a lower probability.",
      driver_deltas: [],
    },
  ],
  rejected_scenarios: [],
  unsimulatable_interventions: [],
};

describe("WhatIfPanel", () => {
  it("shows the baseline and disclaimer from the API payload", () => {
    render(
      <WhatIfPanel
        result={RESULT}
        selectedId="two_year_contract"
        onSelect={vi.fn()}
      />
    );
    expect(screen.getAllByText("80.64%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("49.84%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("-30.80 pp").length).toBeGreaterThan(0);
    expect(screen.getByText("Current")).toBeInTheDocument();
    expect(screen.getByText("Hypothetical")).toBeInTheDocument();
    expect(
      screen.getAllByText(/Model-based what-if estimate — not a causal prediction/).length
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("Move to Two-Year Contract").length).toBeGreaterThan(0);
    expect(screen.getByText("Available interventions")).toBeInTheDocument();
    expect(screen.getByText("+0.4077")).toBeInTheDocument();
    expect(screen.getByText("-1.0255")).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: /Move to One-Year Contract/i }).length
    ).toBeGreaterThan(0);
  });

  it("selects an intervention from the available list", async () => {
    const onSelect = vi.fn();
    render(
      <WhatIfPanel
        result={RESULT}
        selectedId="two_year_contract"
        onSelect={onSelect}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: /Move to One-Year Contract/i }));
    expect(onSelect).toHaveBeenCalledWith("annual_contract");
  });
});
