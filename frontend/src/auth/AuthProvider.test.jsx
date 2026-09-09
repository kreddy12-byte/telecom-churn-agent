import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const loginWithRedirect = vi.fn();
const auth0Logout = vi.fn();
let auth0ProviderProps;

vi.mock("@auth0/auth0-react", () => ({
  Auth0Provider: (props) => {
    auth0ProviderProps = props;
    return props.children;
  },
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

const routerFuture = { v7_startTransition: true, v7_relativeSplatPath: true };

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>;
}

describe("AuthProvider signup", () => {
  beforeEach(() => {
    loginWithRedirect.mockClear();
    auth0ProviderProps = undefined;
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
      <MemoryRouter future={routerFuture}>
        <AuthProvider>
          <SignupControl />
        </AuthProvider>
      </MemoryRouter>
    );
    await userEvent.click(screen.getByRole("button", { name: "Sign up" }));
    expect(loginWithRedirect).toHaveBeenCalledWith({
      appState: { returnTo: "/" },
      authorizationParams: { screen_hint: "signup" },
    });
  });

  it("persists the Auth0 cache in localStorage and navigates with React Router after callback", async () => {
    const { default: AuthProvider } = await import("./AuthProvider");

    render(
      <MemoryRouter initialEntries={["/callback?code=abc&state=xyz"]} future={routerFuture}>
        <AuthProvider>
          <LocationProbe />
        </AuthProvider>
      </MemoryRouter>
    );

    expect(auth0ProviderProps.cacheLocation).toBe("localstorage");
    expect(auth0ProviderProps.useRefreshTokens).toBe(true);

    act(() => {
      auth0ProviderProps.onRedirectCallback({ returnTo: "/customers" });
    });
    expect(screen.getByTestId("location")).toHaveTextContent("/customers");

    act(() => {
      auth0ProviderProps.onRedirectCallback();
    });
    expect(screen.getByTestId("location")).toHaveTextContent("/");
  });
});
