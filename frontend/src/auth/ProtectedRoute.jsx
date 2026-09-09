import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthProvider";

export default function ProtectedRoute({ children }) {
  const { isConfigured, isLoading, isAuthenticated, error } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper text-ink">
        <p className="text-sm text-ink-muted">Checking your session…</p>
      </div>
    );
  }

  if (error && !isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper px-6 text-ink">
        <div className="surface max-w-md p-6">
          <h1 className="text-base font-semibold">Sign-in could not be completed</h1>
          <p className="mt-2 text-sm leading-6 text-ink-muted">
            The identity provider returned an error. Return to login and try again.
            Provider passwords are never collected in this application.
          </p>
          <a href="/login" className="mt-4 inline-block text-sm font-medium text-accent">
            Back to login
          </a>
        </div>
      </div>
    );
  }

  if (!isConfigured || !isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return children;
}
