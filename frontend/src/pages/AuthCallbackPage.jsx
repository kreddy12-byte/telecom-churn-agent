import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";

/**
 * Public landing path for Auth0's authorization-code redirect.
 * Must stay outside ProtectedRoute so the SDK can read `code` before a session exists.
 */
export default function AuthCallbackPage() {
  const { isLoading, isAuthenticated, error } = useAuth();
  const { search } = useLocation();
  const params = new URLSearchParams(search);
  const hasAuthCallback = params.has("code") || params.has("state");

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  if (error) {
    return <Navigate to="/login" replace />;
  }

  if (isLoading || hasAuthCallback) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper text-sm text-ink-muted">
        Completing sign-in…
      </div>
    );
  }

  return <Navigate to="/login" replace />;
}
