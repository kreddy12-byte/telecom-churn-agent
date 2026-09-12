import { beforeEach, describe, expect, it, vi } from "vitest";
import { cachedRequest, clearRequestCache } from "./requestCache";

describe("requestCache", () => {
  beforeEach(() => {
    clearRequestCache();
  });

  it("dedupes concurrent requests for the same key", async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true });
    const first = cachedRequest("demo", fetcher, 60_000);
    const second = cachedRequest("demo", fetcher, 60_000);
    await expect(Promise.all([first, second])).resolves.toEqual([{ ok: true }, { ok: true }]);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("does not keep failed requests in the cache", async () => {
    const fetcher = vi
      .fn()
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValueOnce({ ok: true });
    await expect(cachedRequest("demo", fetcher, 60_000)).rejects.toThrow("boom");
    await expect(cachedRequest("demo", fetcher, 60_000)).resolves.toEqual({ ok: true });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
