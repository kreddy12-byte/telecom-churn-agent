// 1. AUTHENTICATION CONFIGURATION
// Auth0 Universal Login is the only identity source. This file never stores
// passwords and never invents a session when the tenant is unconfigured.
import { createContext, useCallback, useContext, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Auth0Provider, useAuth0 } from "@auth0/auth0-react";
import {
  authCallbackUrl,
  authLogoutReturnUrl,
  markSessionExpired,
  readAuthConfig,
} from "./authConfig";
import { registerSessionExpiredHandler, registerTokenGetter } from "./tokenBridge";

const AuthContext = createContext(null);

const unconfiguredValue = {
  isConfigured: false,
  isLoading: false,
  isAuthenticated: false,
  user: null,
  error: null,
  config: readAuthConfig(),
  loginWithProvider: async () => {},
  loginWithHosted: async () => {},
  loginWithDatabase: async () => {},
  signup: async () => {},
  logout: async () => {},
};

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used within AuthProvider.");
  }
  return value;
}

function mapAuth0User(auth0User) {
  if (!auth0User) {
    return null;
  }
  return {
    sub: auth0User.sub || "",
    name: auth0User.name || auth0User.nickname || "",
    email: auth0User.email || "",
    picture: auth0User.picture || "",
    role: null,
  };
}

function Auth0Bridge({ children, config }) {
  const {
    isLoading,
    isAuthenticated,
    user,
    error,
    loginWithRedirect,
    logout: auth0Logout,
    getAccessTokenSilently,
  } = useAuth0();

  // 2. LOGIN / LOGOUT — always hosted Auth0; credentials never POST to FastAPI.
  const loginWithHosted = useCallback(
    (appState = {}) =>
      loginWithRedirect({
        appState: { returnTo: appState.returnTo || "/" },
        authorizationParams: {
          screen_hint: appState.screenHint,
          login_hint: appState.loginHint,
        },
      }),
    [loginWithRedirect]
  );

  const loginWithProvider = useCallback(
    (connection) =>
      loginWithRedirect({
        appState: { returnTo: "/" },
        authorizationParams: { connection },
      }),
    [loginWithRedirect]
  );

  const loginWithDatabase = useCallback(
    (email) =>
      loginWithRedirect({
        appState: { returnTo: "/" },
        authorizationParams: {
          connection: config.databaseConnection,
          login_hint: email || undefined,
          screen_hint: "login",
        },
      }),
    [config.databaseConnection, loginWithRedirect]
  );

  const signup = useCallback(
    () =>
      loginWithRedirect({
        appState: { returnTo: "/" },
        authorizationParams: { screen_hint: "signup" },
      }),
    [loginWithRedirect]
  );

  const logout = useCallback(() => {
    registerTokenGetter(async () => null);
    auth0Logout({
      logoutParams: {
        returnTo: authLogoutReturnUrl(),
      },
    });
  }, [auth0Logout]);

  // 3. TOKEN RETRIEVAL — silent Auth0 access token for Axios; no local JWT minting.
  useEffect(() => {
    registerTokenGetter(async (options = {}) => {
      if (!isAuthenticated) {
        return null;
      }
      return getAccessTokenSilently({
        cacheMode: options.ignoreCache ? "off" : "on",
        authorizationParams: config.audience ? { audience: config.audience } : undefined,
      });
    });
    registerSessionExpiredHandler(() => {
      markSessionExpired();
      auth0Logout({
        logoutParams: {
          returnTo: authLogoutReturnUrl(),
        },
      });
    });
    return () => {
      registerTokenGetter(async () => null);
      registerSessionExpiredHandler(() => {});
    };
  }, [auth0Logout, config.audience, getAccessTokenSilently, isAuthenticated]);

  const value = useMemo(
    () => ({
      isConfigured: true,
      isLoading,
      isAuthenticated,
      user: mapAuth0User(user),
      error: error ? error.message : null,
      config,
      loginWithProvider,
      loginWithHosted,
      loginWithDatabase,
      signup,
      logout,
    }),
    [
      config,
      error,
      isAuthenticated,
      isLoading,
      loginWithDatabase,
      loginWithHosted,
      loginWithProvider,
      logout,
      signup,
      user,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export default function AuthProvider({ children }) {
  const config = readAuthConfig();
  const navigate = useNavigate();

  if (!config.configured) {
    return <AuthContext.Provider value={{ ...unconfiguredValue, config }}>{children}</AuthContext.Provider>;
  }

  // 2. AUTH0 PROVIDER SETUP
  // Audience is VITE_AUTH0_AUDIENCE so Auth0 mints an API access token for
  // FastAPI. Domain and client ID are also env-only; no client secret here.
  // localStorage keeps the refresh token across reloads; memory cache dies on
  // refresh and silent iframe auth is blocked as a third-party cookie on Vercel.
  return (
    <Auth0Provider
      domain={config.domain}
      clientId={config.clientId}
      authorizationParams={{
        redirect_uri: authCallbackUrl() || undefined,
        audience: config.audience || undefined,
        scope: "openid profile email",
      }}
      cacheLocation="localstorage"
      useRefreshTokens
      onRedirectCallback={(appState) => {
        navigate(appState?.returnTo || "/", { replace: true });
      }}
    >
      <Auth0Bridge config={config}>{children}</Auth0Bridge>
    </Auth0Provider>
  );
}
