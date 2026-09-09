import axios from "axios";
import { getAccessToken, notifySessionExpired } from "../auth/tokenBridge";

/**
 * Shared Axios instance. Base URL comes from VITE_API_BASE_URL.
 * Empty means "same origin", which is how the Vite proxy reaches FastAPI.
 * LLM keys never belong here. Access tokens are attached centrally.
 */
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
  headers: { "Content-Type": "application/json" },
  timeout: 20000,
});

export function apiErrorMessage(error) {
  const payload = error.response?.data?.error;
  if (payload?.message) {
    return payload.message;
  }
  if (error.code === "ECONNABORTED") {
    return "The request took too long. Please try again.";
  }
  if (!error.response) {
    return "Unable to reach the API. Confirm the backend is running.";
  }
  return "The request could not be completed.";
}

export async function attachAccessToken(config) {
  const token = await getAccessToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}

apiClient.interceptors.request.use(attachAccessToken);

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config || {};
    const status = error.response?.status;
    if (status !== 401 || original._retry) {
      return Promise.reject(error);
    }
    original._retry = true;
    const refreshed = await getAccessToken({ ignoreCache: true });
    if (refreshed) {
      original.headers = original.headers || {};
      original.headers.Authorization = `Bearer ${refreshed}`;
      return apiClient(original);
    }
    const path = typeof window !== "undefined" ? window.location.pathname : "";
    if (path !== "/login" && path !== "/callback") {
      notifySessionExpired();
    }
    return Promise.reject(error);
  }
);

export default apiClient;
