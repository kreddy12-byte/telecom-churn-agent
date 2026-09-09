import { describe, expect, it } from "vitest";
import { featureLabel, formatCount, formatPageRange, formatPercent, formatPoints, formatShare, formatShap, strategyLabel } from "./format";

describe("format helpers", () => {
  it("formats the verification probability without inventing digits", () => {
    expect(formatPercent(0.8064)).toBe("80.64%");
  });

  it("formats counts with grouping separators", () => {
    expect(formatCount(7043)).toBe("7,043");
    expect(formatCount(2350)).toBe("2,350");
  });

  it("formats a share of a total to one decimal", () => {
    expect(formatShare(2350, 7043)).toBe("33.4%");
    expect(formatShare(1718, 7043)).toBe("24.4%");
    expect(formatShare(2975, 7043)).toBe("42.2%");
  });

  it("formats percentage-point change with a sign", () => {
    expect(formatPoints(-0.308)).toBe("-30.80 pp");
  });

  it("formats signed SHAP values to four decimals", () => {
    expect(formatShap(1.3752)).toBe("+1.3752");
    expect(formatShap(-0.6895)).toBe("-0.6895");
  });

  it("turns catalogue ids into readable labels", () => {
    expect(strategyLabel("EARLY_LIFECYCLE_ONBOARDING")).toBe(
      "Early Lifecycle Onboarding"
    );
  });

  it("formats a pagination slice from existing total and offset", () => {
    expect(formatPageRange(7043, 0, 20)).toBe("1–20 of 7043");
  });

  it("maps model feature names to dashboard labels", () => {
    expect(featureLabel("tenure")).toBe("Tenure");
    expect(featureLabel("MonthlyCharges")).toBe("Monthly Charges");
    expect(featureLabel("InternetService")).toBe("Internet Service");
    expect(featureLabel("Contract")).toBe("Contract Type");
    expect(featureLabel("TotalCharges")).toBe("Total Charges");
    expect(featureLabel("PaymentMethod")).toBe("Payment Method");
  });
});
