import { createContext, useContext, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthProvider";
import { getMe } from "../services/api";

const ReviewerProfileContext = createContext(null);

export function useReviewerProfile() {
  return useContext(ReviewerProfileContext);
}

export default function ReviewerRoute({ children }) {
  const { isAuthenticated } = useAuth();
  const [status, setStatus] = useState("loading");
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    if (!isAuthenticated) {
      return undefined;
    }
    let cancelled = false;
    setStatus("loading");
    getMe()
      .then((me) => {
        if (cancelled) {
          return;
        }
        setProfile(me);
        setStatus("allowed");
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        setProfile(null);
        if (error.response?.status === 401) {
          setStatus("unauthenticated");
          return;
        }
        // Network or API errors must not block an authenticated session.
        setStatus("allowed");
      });
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated]);

  if (!isAuthenticated || status === "unauthenticated") {
    return <Navigate to="/login" replace />;
  }

  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper text-ink">
        <p className="text-sm text-ink-muted">Checking your session…</p>
      </div>
    );
  }

  return (
    <ReviewerProfileContext.Provider value={profile}>
      {children}
    </ReviewerProfileContext.Provider>
  );
}
