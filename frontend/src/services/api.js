// ============================================================
// 1. API SERVICE
// ============================================================
//
// Every intelligence number the UI shows comes through these functions.
// Components never call axios directly and never talk to an LLM provider.

import apiClient, { apiErrorMessage } from "./apiClient";
import { cachedRequest } from "./requestCache";

export { apiErrorMessage };

export function getHealth() {
  return cachedRequest("health", () =>
    apiClient.get("/health").then((response) => response.data)
  , 30_000);
}

export function getMe() {
  return apiClient.get("/api/me").then((response) => response.data);
}

export function getOverview() {
  return apiClient.get("/api/overview").then((response) => response.data);
}

export function getPredictionSummary() {
  return apiClient.get("/api/predictions/summary").then((response) => response.data);
}

export function getPredictionDistribution() {
  return apiClient.get("/api/predictions/distribution").then((response) => response.data);
}

export function getGlobalImportance(topK = 8) {
  return apiClient
    .get("/api/explanations/global-importance", { params: { top_k: topK } })
    .then((response) => response.data);
}

export function getPredictionRanking({ risk, limit = 10, offset = 0 } = {}) {
  return apiClient
    .get("/api/predictions/ranking", {
      params: {
        risk: risk || undefined,
        limit,
        offset,
      },
    })
    .then((response) => response.data);
}

export function runBatchPredictions() {
  // Scoring the full customer table is slower than a single /api/predict call.
  // The dashboard never starts this on mount — only an explicit reviewer click.
  return apiClient
    .post("/api/predictions/batch", {}, { timeout: 180000 })
    .then((response) => response.data);
}

export function getModelInfo() {
  // Model metadata is static for a deployment; cache avoids AppShell + page double-fetch.
  return cachedRequest("model-info", () =>
    apiClient.get("/api/model").then((response) => response.data)
  , 60_000);
}

export function getCustomers({ limit = 20, offset = 0, q, riskLevel } = {}) {
  return apiClient
    .get("/api/customers", {
      params: {
        limit,
        offset,
        q: q || undefined,
        risk_level: riskLevel || undefined,
      },
    })
    .then((response) => response.data);
}

export function getCustomer(customerId) {
  return apiClient.get(`/api/customers/${customerId}`).then((response) => response.data);
}

export function predictCustomer(customerId) {
  return apiClient
    .post("/api/predict", { customer_id: customerId }, { timeout: 60000 })
    .then((response) => response.data);
}

export function getExplanation(customerId, topK = 5) {
  return apiClient
    .get(`/api/customers/${customerId}/explanation`, {
      params: { top_k: topK },
      timeout: 60000,
    })
    .then((response) => response.data);
}

export function getRecommendation(customerId, { detailed = true } = {}) {
  return apiClient
    .post(
      "/api/recommendation",
      { customer_id: customerId, detailed },
      { timeout: 60000 }
    )
    .then((response) => response.data);
}

export function runWhatIf(customerId, payload = {}) {
  return apiClient
    .post(
      "/api/what-if",
      {
        customer_id: customerId,
        use_llm: false,
        ...payload,
      },
      { timeout: 90000 }
    )
    .then((response) => response.data);
}

export function getActions({ customerId, status, limit = 20, offset = 0 } = {}) {
  return apiClient
    .get("/api/actions", {
      params: {
        customer_id: customerId || undefined,
        status: status || undefined,
        limit,
        offset,
      },
    })
    .then((response) => response.data);
}

export function createAction(payload) {
  return apiClient.post("/api/actions", payload).then((response) => response.data);
}

export function updateAction(actionId, payload) {
  return apiClient
    .patch(`/api/actions/${actionId}`, payload)
    .then((response) => response.data);
}
