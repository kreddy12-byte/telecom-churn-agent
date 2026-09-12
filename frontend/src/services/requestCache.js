/**
 * Tiny in-memory TTL cache for idempotent GETs (e.g. model metadata).
 * Dedupes concurrent callers and avoids a second network hop within the TTL.
 * Not a global app store — callers still own freshness after mutations.
 */

const entries = new Map();

export function cachedRequest(key, fetcher, ttlMs = 60_000) {
  const hit = entries.get(key);
  if (hit && Date.now() - hit.at < ttlMs) {
    return hit.promise;
  }

  const promise = Promise.resolve()
    .then(fetcher)
    .then(
      (data) => {
        entries.set(key, { at: Date.now(), promise: Promise.resolve(data) });
        return data;
      },
      (error) => {
        entries.delete(key);
        throw error;
      }
    );

  entries.set(key, { at: Date.now(), promise });
  return promise;
}

export function clearRequestCache(key) {
  if (key) {
    entries.delete(key);
    return;
  }
  entries.clear();
}
