// 1. AUTHENTICATION CONFIGURATION
// Public Auth0 SPA values only. Client secrets never belong here.

const TRUE = new Set(["1", "true", "yes", "on"]);

function flag(name) {
  return TRUE.has(String(import.meta.env[name] || "").trim().toLowerCase());
}

export const CALLBACK_PATH = "/callback";

export function readAuthConfig() {
  const domain = String(import.meta.env.VITE_AUTH0_DOMAIN || "").trim();
  const clientId = String(import.meta.env.VITE_AUTH0_CLIENT_ID || "").trim();
  const audience = String(import.meta.env.VITE_AUTH0_AUDIENCE || "").trim();
  // EMAIL_ENABLED is the documented flag; DATABASE_ENABLED remains as an alias
  // so existing local .env files keep working.
  const emailEnabled = flag("VITE_AUTH0_EMAIL_ENABLED") || flag("VITE_AUTH0_DATABASE_ENABLED");

  return {
    domain,
    clientId,
    audience,
    configured: Boolean(domain && clientId),
    googleEnabled: flag("VITE_AUTH0_GOOGLE_ENABLED"),
    microsoftEnabled: flag("VITE_AUTH0_MICROSOFT_ENABLED"),
    githubEnabled: flag("VITE_AUTH0_GITHUB_ENABLED"),
    emailEnabled,
    databaseEnabled: emailEnabled,
    signupEnabled: flag("VITE_AUTH0_SIGNUP_ENABLED"),
    googleConnection: import.meta.env.VITE_AUTH0_GOOGLE_CONNECTION || "google-oauth2",
    microsoftConnection: import.meta.env.VITE_AUTH0_MICROSOFT_CONNECTION || "windowslive",
    githubConnection: import.meta.env.VITE_AUTH0_GITHUB_CONNECTION || "github",
    databaseConnection:
      import.meta.env.VITE_AUTH0_DATABASE_CONNECTION || "Username-Password-Authentication",
  };
}

export function authCallbackUrl() {
  if (typeof window === "undefined") {
    return "";
  }
  return `${window.location.origin}${CALLBACK_PATH}`;
}

export function authLogoutReturnUrl() {
  // Must match Allowed Logout URLs on the Auth0 SPA exactly.
  if (typeof window === "undefined") {
    return "";
  }
  return window.location.origin;
}

export const SESSION_EXPIRED_KEY = "ri.sessionExpired";

export function markSessionExpired() {
  try {
    sessionStorage.setItem(SESSION_EXPIRED_KEY, "1");
  } catch {
    /* ignore quota / private mode */
  }
}

export function consumeSessionExpired() {
  try {
    const flagged = sessionStorage.getItem(SESSION_EXPIRED_KEY) === "1";
    if (flagged) {
      sessionStorage.removeItem(SESSION_EXPIRED_KEY);
    }
    return flagged;
  } catch {
    return false;
  }
}
