import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { getMe } from "./services/api";

const logout = vi.fn();

const authState = {
  isConfigured: true,
  isLoading: false,
  isAuthenticated: true,
  user: {
    sub: "auth0|ada",
    name: "Ada Reviewer",
    email: "ada@example.test",
    picture: "",
  },
  error: null,
  config: {
    googleEnabled: false,
    microsoftEnabled: false,
    githubEnabled: false,
    emailEnabled: false,
    databaseEnabled: false,
    signupEnabled: false,
  },
  logout,
  loginWithProvider: vi.fn(),
  loginWithHosted: vi.fn(),
  loginWithDatabase: vi.fn(),
  signup: vi.fn(),
};

vi.mock("./auth/AuthProvider", () => ({
  default: ({ children }) => children,
  useAuth: () => authState,
}));

vi.mock("./services/api", () => ({
  getHealth: vi.fn().mockResolvedValue({ status: "healthy" }),
  getModelInfo: vi.fn().mockResolvedValue({ model_version: "1.0.0", metrics: {} }),
  getMe: vi.fn().mockResolvedValue({
    sub: "auth0|ada",
    name: "Ada Reviewer",
    email: "ada@example.test",
    picture: null,
    role: "REVIEWER",
  }),
  getOverview: vi.fn().mockResolvedValue({
    customer_count: 3,
    evaluated_count: 1,
    risk_counts: { HIGH: 1, MEDIUM: 0, LOW: 0 },
    action_counts: { PENDING: 0 },
    recent_high_risk: [],
  }),
  getPredictionSummary: vi.fn().mockResolvedValue({
    total_scored: 1,
    risk_counts: { HIGH: 1, MEDIUM: 0, LOW: 0 },
    average_churn_probability: 0.8,
    highest_churn_probability: 0.8,
  }),
  getPredictionRanking: vi.fn().mockResolvedValue({
    items: [],
    meta: { total: 0, limit: 10, offset: 0 },
  }),
  getPredictionDistribution: vi.fn().mockResolvedValue({
    total_scored: 1,
    buckets: [
      { bucket: "0-10%", count: 0 },
      { bucket: "10-20%", count: 0 },
      { bucket: "20-30%", count: 0 },
      { bucket: "30-40%", count: 0 },
      { bucket: "40-50%", count: 0 },
      { bucket: "50-60%", count: 0 },
      { bucket: "60-70%", count: 0 },
      { bucket: "70-80%", count: 0 },
      { bucket: "80-90%", count: 1 },
      { bucket: "90-100%", count: 0 },
    ],
  }),
  getGlobalImportance: vi.fn().mockResolvedValue({
    explained_output: "log_odds",
    drivers: [{ feature: "tenure", mean_absolute_shap: 1.02, mean_signed_shap: -0.1 }],
  }),
  runBatchPredictions: vi.fn(),
  getCustomers: vi.fn().mockResolvedValue({ items: [], meta: { total: 0, limit: 20, offset: 0 } }),
  getActions: vi.fn().mockResolvedValue({ items: [], meta: { total: 0, limit: 20, offset: 0 } }),
}));

describe("application shell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.isAuthenticated = true;
    authState.isLoading = false;
    authState.user = {
      sub: "auth0|ada",
      name: "Ada Reviewer",
      email: "ada@example.test",
      picture: "",
    };
    getMe.mockResolvedValue({
      sub: "auth0|ada",
      name: "Ada Reviewer",
      email: "ada@example.test",
      picture: null,
      role: "REVIEWER",
    });
  });

  it("renders primary navigation labels", async () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByText("Retention Intelligence")).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Primary" });
    expect(within(nav).getByRole("link", { name: "Overview" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Customers" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Retention actions" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Model information" })).toBeInTheDocument();
    expect(await screen.findByText("REVIEWER")).toBeInTheDocument();
  });

  it("shows the authenticated user profile in the top bar", async () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByText("Ada Reviewer")).toBeInTheDocument();
    expect(screen.getByText("ada@example.test")).toBeInTheDocument();
    expect(await screen.findByText("REVIEWER")).toBeInTheDocument();
  });

  it("shows the application without a REVIEWER badge when the role is absent", async () => {
    getMe.mockResolvedValue({
      sub: "auth0|sam",
      name: "Sam Signup",
      email: "sam@example.test",
      picture: null,
      role: null,
    });
    render(
      <MemoryRouter
        initialEntries={["/customers"]}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByRole("navigation", { name: "Primary" })).toBeInTheDocument();
    expect(screen.queryByText("Access pending")).not.toBeInTheDocument();
    expect(screen.queryByText("REVIEWER")).not.toBeInTheDocument();
    expect(screen.getByText("Sam Signup")).toBeInTheDocument();
  });

  it("shows ADMIN in the top bar when /api/me returns ADMIN", async () => {
    getMe.mockResolvedValue({
      sub: "auth0|admin",
      name: "Ada Reviewer",
      email: "ada@example.test",
      picture: null,
      role: "ADMIN",
    });
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByText("ADMIN")).toBeInTheDocument();
    expect(screen.queryByText("Access pending")).not.toBeInTheDocument();
  });

  it("sends unauthenticated visitors to login", async () => {
    authState.isAuthenticated = false;
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByRole("button", { name: "Sign in with Auth0" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign up" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Primary" })).not.toBeInTheDocument();
  });

  it("signs out from the application shell", async () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <App />
      </MemoryRouter>
    );
    await userEvent.click(await screen.findByRole("button", { name: /Ada Reviewer/i }));
    await userEvent.click(screen.getByRole("menuitem", { name: "Sign out" }));
    expect(logout).toHaveBeenCalledTimes(1);
  });
});
