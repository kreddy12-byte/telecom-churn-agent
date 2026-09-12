import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../../auth/AuthProvider";
import { useReviewerProfile } from "../../auth/ReviewerRoute";
import { getHealth, getModelInfo } from "../../services/api";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

function RouteFrame({ children }) {
  const location = useLocation();
  return (
    <div key={location.pathname} className="shell-route-enter">
      {children}
    </div>
  );
}

export default function AppShell() {
  const { user, logout } = useAuth();
  const reviewerProfile = useReviewerProfile();
  const location = useLocation();
  const [health, setHealth] = useState(null);
  const [modelVersion, setModelVersion] = useState(null);
  const [navOpen, setNavOpen] = useState(false);
  const profile = reviewerProfile || user;

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: "unavailable" }));
    getModelInfo()
      .then((info) => setModelVersion(info.model_version))
      .catch(() => setModelVersion(null));
  }, []);

  // Close mobile nav after route changes.
  useEffect(() => {
    setNavOpen(false);
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen bg-paper text-ink">
      <Sidebar
        open={navOpen}
        onClose={() => setNavOpen(false)}
        user={profile}
        role={reviewerProfile?.role}
        onSignOut={logout}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          health={health}
          modelVersion={modelVersion}
          navOpen={navOpen}
          navPanelId="app-sidebar"
          onOpenNav={() => setNavOpen((value) => !value)}
        />
        <main className="flex-1 overflow-x-hidden px-4 py-6 sm:px-5 lg:px-8 lg:py-7">
          <div className="mx-auto w-full max-w-content">
            <RouteFrame>
              <Outlet context={{ profile }} />
            </RouteFrame>
          </div>
        </main>
      </div>
    </div>
  );
}
