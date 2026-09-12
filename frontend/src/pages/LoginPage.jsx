import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import Button from "../components/common/Button";
import { consumeSessionExpired } from "../auth/authConfig";
import { useAuth } from "../auth/AuthProvider";

export default function LoginPage() {
  const { isConfigured, isAuthenticated, isLoading, loginWithHosted, signup } = useAuth();
  const [sessionExpired, setSessionExpired] = useState(false);

  useEffect(() => {
    setSessionExpired(consumeSessionExpired());
  }, []);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper text-sm text-ink-muted">
        Checking your session…
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-4 py-10 text-ink">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <p className="text-[13px] font-semibold tracking-tight text-ink">Churn Intelligence</p>
          <p className="mt-1 text-sm text-ink-muted">AI-powered customer risk platform</p>
        </div>

        <div className="surface p-6 sm:p-7">
          {sessionExpired ? (
            <p className="mb-4 rounded-panel border border-warning/35 bg-warning-soft px-3 py-2 text-sm text-warning">
              Your session has expired. Please sign in again.
            </p>
          ) : null}

          {!isConfigured ? (
            <p className="rounded-panel border border-line bg-surface-muted px-3 py-2 text-sm text-ink-muted">
              Auth0 is not configured for this environment. Set{" "}
              <code className="text-xs">VITE_AUTH0_DOMAIN</code> and{" "}
              <code className="text-xs">VITE_AUTH0_CLIENT_ID</code>. See
              docs/AUTHENTICATION.md.
            </p>
          ) : (
            <>
              <Button
                type="button"
                variant="primary"
                className="w-full justify-center py-2.5"
                onClick={() => loginWithHosted()}
              >
                Sign in with Auth0
              </Button>
              <p className="mt-4 text-center text-sm text-ink-muted">
                Don&apos;t have an account?
              </p>
              <Button
                type="button"
                variant="secondary"
                className="mt-2 w-full justify-center py-2.5"
                onClick={() => signup()}
              >
                Sign up
              </Button>
            </>
          )}
        </div>

        <p className="mt-4 text-center text-xs text-ink-faint">
          ML predicts · SHAP explains · AI recommends · What-if evaluates · Human approves
        </p>
        <p className="mt-6 text-center">
          <Link to="/" className="text-xs text-ink-faint hover:text-ink-muted">
            Churn Intelligence
          </Link>
        </p>
      </div>
    </div>
  );
}
