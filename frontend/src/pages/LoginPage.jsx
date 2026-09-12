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
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-paper px-4 py-10 text-ink">
      <div
        className="pointer-events-none absolute -left-24 top-0 h-64 w-64 rounded-full bg-accent/10 blur-3xl"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute -right-16 bottom-10 h-56 w-56 rounded-full bg-accent-secondary/10 blur-3xl"
        aria-hidden="true"
      />
      <div className="relative w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-panel bg-accent-soft text-sm font-bold text-accent ring-1 ring-accent/20 shadow-sm">
            CI
          </div>
          <p className="text-xl font-semibold tracking-tight text-ink">Churn Intelligence</p>
          <p className="mt-2 text-sm leading-6 text-ink-muted">
            AI-powered customer risk platform
          </p>
        </div>

        <div className="surface-elevated p-6 sm:p-8">
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
