import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Customers from "./Customers";
import { getCustomers } from "../services/api";

vi.mock("../services/api", () => ({
  apiErrorMessage: (err) => err.message || "Unable to load.",
  getCustomers: vi.fn(),
}));

const CUSTOMERS = {
  items: [
    {
      customer_id: "7590-VHVEG",
      contract: "Month-to-month",
      tenure: 1,
      monthly_charges: 29.85,
      latest_prediction: { churn_probability: 0.8064, risk_level: "HIGH" },
    },
    {
      customer_id: "0004-TLHLJ",
      contract: "One year",
      tenure: 12,
      monthly_charges: 70,
      latest_prediction: { churn_probability: 0.42, risk_level: "MEDIUM" },
    },
  ],
  meta: { total: 2, limit: 20, offset: 0 },
};

function renderCustomers(path = "/customers") {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/customers" element={<Customers />} />
        <Route path="/customers/:customerId" element={<div>Detail {path}</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("Customer Intelligence list", () => {
  beforeEach(() => {
    getCustomers.mockReset();
    getCustomers.mockResolvedValue(CUSTOMERS);
  });

  it("renders the intelligence workspace and customer risk table", async () => {
    renderCustomers();
    expect(
      await screen.findByRole("heading", { name: "Customer Intelligence" })
    ).toBeInTheDocument();
    expect(await screen.findByText("7590-VHVEG")).toBeInTheDocument();
    expect(screen.getByText("80.64%")).toBeInTheDocument();
    expect(screen.getByText("HIGH risk")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /View intelligence for 7590-VHVEG/i })).toHaveAttribute(
      "href",
      "/customers/7590-VHVEG"
    );
  });

  it("keeps customer search wired to the customers API", async () => {
    renderCustomers();
    await screen.findByText("7590-VHVEG");
    await userEvent.clear(screen.getByLabelText("Customer ID"));
    await userEvent.type(screen.getByLabelText("Customer ID"), "TLHL");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() => {
      expect(getCustomers).toHaveBeenCalledWith(
        expect.objectContaining({ q: "TLHL", limit: 20, offset: 0 })
      );
    });
  });
});
