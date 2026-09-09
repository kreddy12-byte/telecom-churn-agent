import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";

/**
 * Public landing path for Auth0's authorization-code redirect.
 * Must stay outside ProtectedRoute so the SDK can read `code` before a session exists.
 */
export default function AuthCallbackPage() {
  const { isLoading, isAuthenticated, error } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper text-sm text-ink-muted">
        Completing sign-in…
      </div>
    );
  }

  if (error) {
    return <Navigate to="/login" replace />;
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <Navigate to="/login" replace />;
}
