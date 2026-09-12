import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import LoginPage from "./LoginPage";
import { consumeSessionExpired } from "../auth/authConfig";

const loginWithHosted = vi.fn();
const signup = vi.fn();

const authState = {
  isConfigured: true,
  isAuthenticated: false,
  isLoading: false,
  user: null,
  error: null,
  config: {},
  loginWithHosted,
  signup,
  logout: vi.fn(),
};

vi.mock("../auth/AuthProvider", () => ({
  useAuth: () => authState,
}));

vi.mock("../auth/authConfig", async () => {
  const actual = await vi.importActual("../auth/authConfig");
  return {
    ...actual,
    consumeSessionExpired: vi.fn(() => false),
  };
});

function renderLogin() {
  return render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <LoginPage />
    </MemoryRouter>
  );
}

describe("LoginPage", () => {
  it("keeps sign-in disabled when Auth0 is unconfigured", () => {
    authState.isConfigured = false;
    try {
      renderLogin();
      expect(screen.queryByRole("button", { name: "Sign in with Auth0" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Sign up" })).not.toBeInTheDocument();
      expect(screen.getByText(/Auth0 is not configured for this environment/i)).toBeInTheDocument();
    } finally {
      authState.isConfigured = true;
    }
  });

  it("renders Sign in with Auth0 and Sign up without a local password form", async () => {
    renderLogin();
    expect(screen.getAllByText("Churn Intelligence").length).toBeGreaterThan(0);
    expect(screen.getByText("AI-powered customer risk platform")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in with Auth0" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Sign up" })).toBeEnabled();
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Continue with Google" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Sign in with Auth0" }));
    expect(loginWithHosted).toHaveBeenCalled();

    expect(screen.getByText(/Don't have an account/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sign up" }));
    expect(signup).toHaveBeenCalledTimes(1);
  });

  it("shows a session-expired message when the API rejected the token", () => {
    consumeSessionExpired.mockReturnValueOnce(true);
    renderLogin();
    expect(
      screen.getByText("Your session has expired. Please sign in again.")
    ).toBeInTheDocument();
  });
});
