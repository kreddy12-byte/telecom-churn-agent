import { beforeEach, describe, expect, it } from "vitest";
import { attachAccessToken } from "./apiClient";
import { registerTokenGetter } from "../auth/tokenBridge";

describe("API token attachment", () => {
  beforeEach(() => {
    registerTokenGetter(async () => null);
  });

  it("attaches a bearer token when Auth0 has issued one", async () => {
    registerTokenGetter(async () => "access-token-example");
    const config = await attachAccessToken({ headers: {} });
    expect(config.headers.Authorization).toBe("Bearer access-token-example");
  });

  it("does not invent a token when the session is empty", async () => {
    const config = await attachAccessToken({ headers: {} });
    expect(config.headers.Authorization).toBeUndefined();
  });
});
