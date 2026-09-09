import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import DecisionPanel from "./DecisionPanel";

const BASE = {
  customerId: "7590-VHVEG",
  recommendation: {
    selected_strategy: {
      strategy_id: "EARLY_LIFECYCLE_ONBOARDING",
      strategy_name: "Early Lifecycle Onboarding",
    },
    recommendation: "Arrange a personalised onboarding review.",
  },
  probability: 0.8064,
  currentAction: null,
  busy: false,
};

function renderPanel(props) {
  return render(
    <MemoryRouter>
      <DecisionPanel {...BASE} {...props} />
    </MemoryRouter>
  );
}

describe("DecisionPanel", () => {
  it("confirms approval against the recommended strategy", async () => {
    const onApprove = vi.fn().mockResolvedValue();
    renderPanel({ onApprove });

    await userEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(screen.getByText(/does not contact the customer/i)).toBeInTheDocument();
    expect(screen.getByText(/80\.64%/)).toBeInTheDocument();
    expect(screen.getByText(/Early Lifecycle Onboarding/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Confirm approval" }));
    expect(onApprove).toHaveBeenCalledTimes(1);
  });

  it("requires a reviewer note before rejecting", async () => {
    const onReject = vi.fn().mockResolvedValue();
    renderPanel({ onReject });

    await userEvent.click(screen.getByRole("button", { name: "Reject" }));
    const confirm = screen.getByRole("button", { name: "Confirm rejection" });
    expect(confirm).toBeDisabled();

    await userEvent.type(screen.getByLabelText(/Reason/i), "Offer is not appropriate.");
    expect(confirm).toBeEnabled();
    await userEvent.click(confirm);
    expect(onReject).toHaveBeenCalledWith("Offer is not appropriate.");
  });

  it("requires a note when the reviewer modifies the strategy", async () => {
    const onModify = vi.fn().mockResolvedValue();
    renderPanel({ onModify });

    await userEvent.click(screen.getByRole("button", { name: "Modify" }));
    const save = screen.getByRole("button", { name: "Save modification" });
    expect(save).toBeDisabled();

    await userEvent.selectOptions(screen.getByLabelText(/Strategy/i), "CONTRACT_CONVERSION");
    await userEvent.type(screen.getByLabelText(/Reviewer note/i), "Prefer a contract conversation.");
    expect(save).toBeEnabled();
    await userEvent.click(save);
    expect(onModify).toHaveBeenCalledWith({
      strategyId: "CONTRACT_CONVERSION",
      recommendation: "Arrange a personalised onboarding review.",
      reviewerNote: "Prefer a contract conversation.",
    });
  });

  it("does not offer a new decision after approval", () => {
    renderPanel({
      currentAction: {
        status: "APPROVED",
        customer_id: "7590-VHVEG",
        strategy_id: "EARLY_LIFECYCLE_ONBOARDING",
        reviewed_by_name: "Ada Reviewer",
        updated_at: "2026-09-09T10:00:00Z",
        reviewer_note: "Proceed.",
      },
      onNewReview: vi.fn(),
    });
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New review" })).toBeInTheDocument();
    expect(screen.getByText("Retention action approved")).toBeInTheDocument();
    expect(screen.getByText("Ada Reviewer")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View retention actions" })).toHaveAttribute(
      "href",
      "/actions"
    );
  });
});
