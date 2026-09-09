import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import RecommendationPanel from "./RecommendationPanel";

describe("RecommendationPanel", () => {
  it("shows the human-approval badge and supplied reasoning", () => {
    render(
      <RecommendationPanel
        recommendation={{
          selected_strategy: {
            strategy_id: "EARLY_LIFECYCLE_ONBOARDING",
            strategy_name: "Early Lifecycle Onboarding",
          },
          recommendation: "Arrange a personalised onboarding review.",
          reasoning: ["Short tenure is the strongest risk-increasing driver."],
          priority: "HIGH",
          confidence: "MEDIUM",
          requires_human_approval: true,
        }}
      />
    );
    expect(screen.getByText(/Human approval required/i)).toBeInTheDocument();
    expect(screen.getByText("Early Lifecycle Onboarding")).toBeInTheDocument();
    expect(screen.getByText("Why this action was selected")).toBeInTheDocument();
    expect(
      screen.getByText("Short tenure is the strongest risk-increasing driver.")
    ).toBeInTheDocument();
  });

  it("labels deterministic fallback reasoning without exposing SHAP internals", () => {
    render(
      <RecommendationPanel
        recommendation={{
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
        }}
      />
    );
    expect(screen.getByText("System-generated fallback reasoning")).toBeInTheDocument();
    expect(screen.getByText(/Tenure = 1 · increases churn risk/)).toBeInTheDocument();
    expect(screen.queryByText(/SHAP 1.3752/)).not.toBeInTheDocument();
  });
});
