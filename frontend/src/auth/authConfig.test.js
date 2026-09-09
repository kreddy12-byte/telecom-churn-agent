import { beforeEach, describe, expect, it, vi } from "vitest";

describe("authConfig flags", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("treats Auth0 as unconfigured without domain and client id", async () => {
    vi.stubEnv("VITE_AUTH0_DOMAIN", "");
    vi.stubEnv("VITE_AUTH0_CLIENT_ID", "");
    const { readAuthConfig } = await import("./authConfig");
    expect(readAuthConfig().configured).toBe(false);
    vi.unstubAllEnvs();
  });

  it("is configured when domain and client id are present", async () => {
    vi.stubEnv("VITE_AUTH0_DOMAIN", "example.auth0.com");
    vi.stubEnv("VITE_AUTH0_CLIENT_ID", "public-client-id");
    const { readAuthConfig } = await import("./authConfig");
    expect(readAuthConfig().configured).toBe(true);
    expect(readAuthConfig().googleEnabled).toBe(false);
    vi.unstubAllEnvs();
  });

  it("reads the FastAPI API audience from VITE_AUTH0_AUDIENCE", async () => {
    vi.stubEnv("VITE_AUTH0_AUDIENCE", "https://telecom-churn-api");
    const { readAuthConfig } = await import("./authConfig");
    expect(readAuthConfig().audience).toBe("https://telecom-churn-api");
    vi.unstubAllEnvs();
  });

  it("enables email/password from VITE_AUTH0_EMAIL_ENABLED", async () => {
    vi.stubEnv("VITE_AUTH0_EMAIL_ENABLED", "true");
    const { readAuthConfig } = await import("./authConfig");
    const config = readAuthConfig();
    expect(config.emailEnabled).toBe(true);
    expect(config.databaseEnabled).toBe(true);
    vi.unstubAllEnvs();
  });
});
