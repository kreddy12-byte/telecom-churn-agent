import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { useAuth } from "../../auth/AuthProvider";
import { useReviewerProfile } from "../../auth/ReviewerRoute";
import { getHealth, getModelInfo } from "../../services/api";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

export default function AppShell() {
  const { user, logout } = useAuth();
  const reviewerProfile = useReviewerProfile();
  const [health, setHealth] = useState(null);
  const [modelVersion, setModelVersion] = useState(null);
  const profile = reviewerProfile || user;

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: "unavailable" }));
    getModelInfo()
      .then((info) => setModelVersion(info.model_version))
      .catch(() => setModelVersion(null));
  }, []);

  return (
    <div className="flex min-h-screen bg-paper text-ink">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          health={health}
          modelVersion={modelVersion}
          user={profile}
          role={reviewerProfile?.role}
          onSignOut={logout}
        />
        <main className="flex-1 overflow-x-hidden px-5 py-5 lg:px-7">
          <div className="mx-auto max-w-6xl">
            <Outlet context={{ profile }} />
          </div>
        </main>
      </div>
    </div>
  );
}
