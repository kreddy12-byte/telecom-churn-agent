import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Actions from "./Actions";
import { getActions, getOverview } from "../services/api";

vi.mock("../services/api", () => ({
  apiErrorMessage: (err) => err.message || "Unable to load.",
  getActions: vi.fn(),
  getOverview: vi.fn(),
}));

describe("Retention actions", () => {
  beforeEach(() => {
    getActions.mockReset();
    getOverview.mockReset();
    getOverview.mockResolvedValue({
      customer_count: 10,
      action_counts: { PENDING: 2, APPROVED: 1, MODIFIED: 0, REJECTED: 1 },
    });
  });

  it("shows an action recorded from customer intelligence", async () => {
    getActions.mockResolvedValue({
      items: [
        {
          id: 12,
          customer_id: "7590-VHVEG",
          strategy_id: "EARLY_LIFECYCLE_ONBOARDING",
          recommendation: "Arrange a personalised onboarding review.",
          status: "APPROVED",
          reviewed_by_name: "Ada Reviewer",
          reviewed_by_email: "ada@example.test",
          reviewer_note: null,
          created_at: "2026-09-09T09:00:00Z",
          updated_at: "2026-09-09T10:00:00Z",
        },
      ],
      meta: { total: 1, limit: 20, offset: 0 },
    });

    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(getActions).toHaveBeenCalled();
    });
    expect(await screen.findByText("7590-VHVEG")).toBeInTheDocument();
    expect(screen.getByText("Early Lifecycle Onboarding")).toBeInTheDocument();
    expect(screen.getByText("Arrange a personalised onboarding review.")).toBeInTheDocument();
    expect(screen.getByText("Ada Reviewer")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Decision" })).toBeInTheDocument();
    expect(screen.getAllByText("APPROVED").length).toBeGreaterThan(0);
    expect(await screen.findByText("Pending")).toBeInTheDocument();
  });

  it("shows a useful error when the action list fails", async () => {
    getActions.mockRejectedValue(new Error("actions unavailable"));
    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>
    );
    expect(await screen.findByText("actions unavailable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
