import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ShapBars from "./ShapBars";

const DRIVERS = [
  { feature: "tenure", value: 1, shap_value: 1.3752, direction: "increases_risk", impact: 0.3 },
  {
    feature: "InternetService",
    value: "DSL",
    shap_value: -0.6895,
    direction: "decreases_risk",
    impact: 0.2,
  },
];

describe("ShapBars", () => {
  it("renders API-supplied SHAP values and directions", () => {
    render(<ShapBars drivers={DRIVERS} />);
    expect(screen.getByText("+1.3752")).toBeInTheDocument();
    expect(screen.getByText("-0.6895")).toBeInTheDocument();
    expect(screen.getAllByText(/Increases churn risk|Decreases churn risk/).length).toBeGreaterThanOrEqual(2);
    expect(
      screen.getByText(
        /SHAP explains how features influenced this model prediction; it does not prove that a feature causes churn/
      )
    ).toBeInTheDocument();
  });
});
