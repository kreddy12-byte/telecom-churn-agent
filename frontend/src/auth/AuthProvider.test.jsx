import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const loginWithRedirect = vi.fn();
const auth0Logout = vi.fn();

vi.mock("@auth0/auth0-react", () => ({
  Auth0Provider: ({ children }) => children,
  useAuth0: () => ({
    isLoading: false,
    isAuthenticated: false,
    user: null,
    error: null,
    loginWithRedirect,
    logout: auth0Logout,
    getAccessTokenSilently: vi.fn(),
  }),
}));

describe("AuthProvider signup", () => {
  beforeEach(() => {
    loginWithRedirect.mockClear();
    vi.resetModules();
    vi.stubEnv("VITE_AUTH0_DOMAIN", "example.auth0.com");
    vi.stubEnv("VITE_AUTH0_CLIENT_ID", "public-spa-client");
  });

  it("redirects to Auth0 Universal Login with screen_hint=signup", async () => {
    const { default: AuthProvider, useAuth } = await import("./AuthProvider");

    function SignupControl() {
      const { signup } = useAuth();
      return (
        <button type="button" onClick={() => signup()}>
          Sign up
        </button>
      );
    }

    render(
      <AuthProvider>
        <SignupControl />
      </AuthProvider>
    );
    await userEvent.click(screen.getByRole("button", { name: "Sign up" }));
    expect(loginWithRedirect).toHaveBeenCalledWith({
      appState: { returnTo: "/" },
      authorizationParams: { screen_hint: "signup" },
    });
  });
});
