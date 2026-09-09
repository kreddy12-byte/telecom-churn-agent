import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReviewerRoute from "./ReviewerRoute";
import { getMe } from "../services/api";

vi.mock("./AuthProvider", () => ({
  useAuth: () => ({
    isAuthenticated: true,
    logout: vi.fn(),
    user: {
      name: "Sam Signup",
      email: "sam@example.test",
    },
  }),
}));

vi.mock("../services/api", () => ({
  getMe: vi.fn(),
}));

function renderAt(path) {
  return render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Routes>
        <Route path="/login" element={<p>Login screen</p>} />
        <Route
          path={path}
          element={
            <ReviewerRoute>
              <p>Application dashboard</p>
            </ReviewerRoute>
          }
        />
      </Routes>
    </MemoryRouter>
  );
}

describe("ReviewerRoute", () => {
  beforeEach(() => {
    getMe.mockReset();
    window.localStorage.clear();
  });

  it("renders the application when /api/me returns REVIEWER", async () => {
    getMe.mockResolvedValue({
      sub: "auth0|ada",
      role: "REVIEWER",
    });
    renderAt("/");
    expect(await screen.findByText("Application dashboard")).toBeInTheDocument();
  });

  it("renders the application when /api/me returns ADMIN", async () => {
    getMe.mockResolvedValue({
      sub: "auth0|admin",
      role: "ADMIN",
    });
    renderAt("/");
    expect(await screen.findByText("Application dashboard")).toBeInTheDocument();
  });

  it("renders the application when the authenticated user has no role", async () => {
    getMe.mockResolvedValue({
      sub: "auth0|sam",
      email: "sam@example.test",
      name: "Sam Signup",
      role: null,
    });
    renderAt("/customers");
    expect(await screen.findByText("Application dashboard")).toBeInTheDocument();
    expect(screen.queryByText("Access pending")).not.toBeInTheDocument();
    expect(screen.queryByText("REVIEWER")).not.toBeInTheDocument();
  });

  it("does not treat a localStorage role as authentication", async () => {
    window.localStorage.setItem("role", "REVIEWER");
    window.localStorage.setItem("ri.role", "REVIEWER");
    getMe.mockResolvedValue({ role: null });
    renderAt("/");
    expect(await screen.findByText("Application dashboard")).toBeInTheDocument();
    expect(screen.queryByText("REVIEWER")).not.toBeInTheDocument();
  });

  it("sends a 401 from /api/me to login", async () => {
    getMe.mockRejectedValue({ response: { status: 401 } });
    renderAt("/");
    expect(await screen.findByText("Login screen")).toBeInTheDocument();
    expect(screen.queryByText("Application dashboard")).not.toBeInTheDocument();
  });

  it("does not block an authenticated user when the API is unreachable", async () => {
    getMe.mockRejectedValue({ message: "Network Error" });
    renderAt("/");
    expect(await screen.findByText("Application dashboard")).toBeInTheDocument();
    expect(screen.queryByText("Unable to verify reviewer access")).not.toBeInTheDocument();
    expect(screen.queryByText("Access pending")).not.toBeInTheDocument();
  });
});
