import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import AuthProvider from "./auth/AuthProvider";
import ProtectedRoute from "./auth/ProtectedRoute";
import ReviewerRoute from "./auth/ReviewerRoute";
import AppShell from "./components/layout/AppShell";
import {
  ActionsSkeleton,
  BatchAnalysisSkeleton,
  CustomerIntelligenceSkeleton,
  CustomersSkeleton,
  OverviewSkeleton,
  PageSkeleton,
} from "./components/common/Skeleton";
import LoginPage from "./pages/LoginPage";
import AuthCallbackPage from "./pages/AuthCallbackPage";

const Overview = lazy(() => import("./pages/Overview"));
const Customers = lazy(() => import("./pages/Customers"));
const CustomerIntelligence = lazy(() => import("./pages/CustomerIntelligence"));
const Actions = lazy(() => import("./pages/Actions"));
const BatchAnalysis = lazy(() => import("./pages/BatchAnalysis"));
const ModelInformation = lazy(() => import("./pages/ModelInformation"));
const ProfilePage = lazy(() => import("./pages/ProfilePage"));
const AccountPage = lazy(() => import("./pages/AccountPage"));

function RouteFallback() {
  const { pathname } = useLocation();

  if (pathname === "/" || pathname === "") {
    return <OverviewSkeleton />;
  }
  if (pathname === "/customers") {
    return <CustomersSkeleton />;
  }
  if (pathname.startsWith("/customers/")) {
    return <CustomerIntelligenceSkeleton />;
  }
  if (pathname === "/actions") {
    return <ActionsSkeleton />;
  }
  if (pathname === "/batch") {
    return (
      <div className="space-y-5">
        <div>
          <div className="h-7 w-48 max-w-full rounded-control bg-surface-interactive/80" aria-hidden="true" />
          <div className="mt-3 h-4 w-96 max-w-full rounded-control bg-surface-interactive/80" aria-hidden="true" />
        </div>
        <BatchAnalysisSkeleton />
      </div>
    );
  }
  return <PageSkeleton />;
}

function LazyPage({ children }) {
  return <Suspense fallback={<RouteFallback />}>{children}</Suspense>;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/callback" element={<AuthCallbackPage />} />
        <Route
          element={
            <ProtectedRoute>
              <ReviewerRoute>
                <AppShell />
              </ReviewerRoute>
            </ProtectedRoute>
          }
        >
          <Route
            index
            element={
              <LazyPage>
                <Overview />
              </LazyPage>
            }
          />
          <Route
            path="customers"
            element={
              <LazyPage>
                <Customers />
              </LazyPage>
            }
          />
          <Route
            path="customers/:customerId"
            element={
              <LazyPage>
                <CustomerIntelligence />
              </LazyPage>
            }
          />
          <Route
            path="actions"
            element={
              <LazyPage>
                <Actions />
              </LazyPage>
            }
          />
          <Route
            path="batch"
            element={
              <LazyPage>
                <BatchAnalysis />
              </LazyPage>
            }
          />
          <Route
            path="model"
            element={
              <LazyPage>
                <ModelInformation />
              </LazyPage>
            }
          />
          <Route
            path="profile"
            element={
              <LazyPage>
                <ProfilePage />
              </LazyPage>
            }
          />
          <Route
            path="account"
            element={
              <LazyPage>
                <AccountPage />
              </LazyPage>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
