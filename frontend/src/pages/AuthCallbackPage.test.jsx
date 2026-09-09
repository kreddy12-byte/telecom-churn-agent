import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import AuthCallbackPage from "./AuthCallbackPage";

const state = {
  isLoading: false,
  isAuthenticated: false,
  error: null,
};

vi.mock("../auth/AuthProvider", () => ({
  useAuth: () => state,
}));

describe("AuthCallbackPage", () => {
  it("shows a completing-sign-in state while Auth0 processes the code", () => {
    state.isLoading = true;
    state.isAuthenticated = false;
    state.error = null;
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <AuthCallbackPage />
      </MemoryRouter>
    );
    expect(screen.getByText("Completing sign-in…")).toBeInTheDocument();
  });
});
