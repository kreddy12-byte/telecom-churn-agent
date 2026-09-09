/**
 * Lets Axios ask for an Auth0 access token without importing React hooks.
 * AuthProvider registers the getter; tests can replace it.
 */

// # 1. TOKEN BRIDGE
let tokenGetter = async () => null;
let onSessionExpired = () => {};

export function registerTokenGetter(fn) {
  tokenGetter = typeof fn === "function" ? fn : async () => null;
}

export function registerSessionExpiredHandler(fn) {
  onSessionExpired = typeof fn === "function" ? fn : () => {};
}

// # 2. TOKEN RETRIEVAL
export async function getAccessToken(options = {}) {
  try {
    return (await tokenGetter(options)) || null;
  } catch {
    return null;
  }
}

export function notifySessionExpired() {
  onSessionExpired();
}
