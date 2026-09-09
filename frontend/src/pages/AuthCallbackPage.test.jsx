import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
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

const routerFuture = { v7_startTransition: true, v7_relativeSplatPath: true };

function renderCallback(path = "/callback") {
  return render(
    <MemoryRouter initialEntries={[path]} future={routerFuture}>
      <Routes>
        <Route path="/callback" element={<AuthCallbackPage />} />
        <Route path="/login" element={<div>login page</div>} />
        <Route path="/" element={<div>home page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("AuthCallbackPage", () => {
  it("shows a completing-sign-in state while Auth0 processes the code", () => {
    state.isLoading = true;
    state.isAuthenticated = false;
    state.error = null;
    renderCallback("/callback?code=abc&state=xyz");
    expect(screen.getByText("Completing sign-in…")).toBeInTheDocument();
  });

  it("does not send the user to login while callback code or state is still in the URL", () => {
    state.isLoading = false;
    state.isAuthenticated = false;
    state.error = null;
    renderCallback("/callback?code=abc&state=xyz");
    expect(screen.getByText("Completing sign-in…")).toBeInTheDocument();
    expect(screen.queryByText("login page")).not.toBeInTheDocument();
  });

  it("redirects to login when the callback finished without a session and without Auth0 params", () => {
    state.isLoading = false;
    state.isAuthenticated = false;
    state.error = null;
    renderCallback("/callback");
    expect(screen.getByText("login page")).toBeInTheDocument();
  });
});
