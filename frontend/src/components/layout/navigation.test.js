import { describe, expect, it } from "vitest";
import { breadcrumbsForPath, isNavActive, PRIMARY_NAV } from "./navigation";

describe("shell navigation helpers", () => {
  it("builds breadcrumbs for nested customer intelligence routes", () => {
    expect(breadcrumbsForPath("/")).toEqual([{ label: "Overview" }]);
    expect(breadcrumbsForPath("/customers")).toEqual([{ label: "Customer Intelligence" }]);
    expect(breadcrumbsForPath("/customers/7590-VHVEG")).toEqual([
      { label: "Customer Intelligence", to: "/customers" },
      { label: "7590-VHVEG" },
    ]);
    expect(breadcrumbsForPath("/actions")).toEqual([{ label: "Retention Actions" }]);
    expect(breadcrumbsForPath("/batch")).toEqual([{ label: "Batch Analysis" }]);
  });

  it("marks Customer Intelligence active for nested customer routes", () => {
    const customers = PRIMARY_NAV.find((item) => item.to === "/customers");
    expect(isNavActive(customers, "/customers")).toBe(true);
    expect(isNavActive(customers, "/customers/7590-VHVEG")).toBe(true);
    expect(isNavActive(customers, "/actions")).toBe(false);
    const batch = PRIMARY_NAV.find((item) => item.to === "/batch");
    expect(isNavActive(batch, "/batch")).toBe(true);
  });
});
