import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import ProtectedRoute from "./ProtectedRoute";

const state = {
  isConfigured: true,
  isLoading: false,
  isAuthenticated: false,
  error: null,
};

vi.mock("./AuthProvider", () => ({
  useAuth: () => state,
}));

describe("ProtectedRoute", () => {
  it("redirects unauthenticated users from customers, actions, and model", () => {
    state.isLoading = false;
    state.isAuthenticated = false;
    state.error = null;

    for (const path of ["/customers", "/actions", "/model", "/customers/7590-VHVEG"]) {
      const { unmount } = render(
        <MemoryRouter
          initialEntries={[path]}
          future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
        >
          <Routes>
            <Route path="/login" element={<p>Login screen</p>} />
            <Route
              path={path}
              element={
                <ProtectedRoute>
                  <p>Secret {path}</p>
                </ProtectedRoute>
              }
            />
          </Routes>
        </MemoryRouter>
      );
      expect(screen.getByText("Login screen")).toBeInTheDocument();
      expect(screen.queryByText(`Secret ${path}`)).not.toBeInTheDocument();
      unmount();
    }
  });

  it("shows a loading state while authentication is resolving", () => {
    state.isLoading = true;
    state.isAuthenticated = false;
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ProtectedRoute>
          <p>Customers secret</p>
        </ProtectedRoute>
      </MemoryRouter>
    );
    expect(screen.getByText("Checking your session…")).toBeInTheDocument();
  });

  it("shows an authentication error when the provider fails", () => {
    state.isLoading = false;
    state.isAuthenticated = false;
    state.error = "redirect_uri mismatch";
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ProtectedRoute>
          <p>Customers secret</p>
        </ProtectedRoute>
      </MemoryRouter>
    );
    expect(screen.getByText("Sign-in could not be completed")).toBeInTheDocument();
    expect(screen.queryByText("redirect_uri mismatch")).not.toBeInTheDocument();
  });

  it("does not treat a localStorage role as a session", () => {
    state.isLoading = false;
    state.isAuthenticated = false;
    state.error = null;
    window.localStorage.setItem("role", "REVIEWER");
    render(
      <MemoryRouter
        initialEntries={["/customers"]}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <Routes>
          <Route path="/login" element={<p>Login screen</p>} />
          <Route
            path="/customers"
            element={
              <ProtectedRoute>
                <p>Secret customers</p>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText("Login screen")).toBeInTheDocument();
    expect(screen.queryByText("Secret customers")).not.toBeInTheDocument();
    window.localStorage.clear();
  });

  it("renders protected content when authenticated", () => {
    state.isLoading = false;
    state.isAuthenticated = true;
    state.error = null;
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ProtectedRoute>
          <p>Customers secret</p>
        </ProtectedRoute>
      </MemoryRouter>
    );
    expect(screen.getByText("Customers secret")).toBeInTheDocument();
  });
});
