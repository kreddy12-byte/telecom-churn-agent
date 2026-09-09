import { Navigate, Route, Routes } from "react-router-dom";
import AuthProvider from "./auth/AuthProvider";
import ProtectedRoute from "./auth/ProtectedRoute";
import ReviewerRoute from "./auth/ReviewerRoute";
import AppShell from "./components/layout/AppShell";
import Overview from "./pages/Overview";
import Customers from "./pages/Customers";
import CustomerIntelligence from "./pages/CustomerIntelligence";
import Actions from "./pages/Actions";
import ModelInformation from "./pages/ModelInformation";
import LoginPage from "./pages/LoginPage";
import AuthCallbackPage from "./pages/AuthCallbackPage";
import ProfilePage from "./pages/ProfilePage";
import AccountPage from "./pages/AccountPage";

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
          <Route index element={<Overview />} />
          <Route path="customers" element={<Customers />} />
          <Route path="customers/:customerId" element={<CustomerIntelligence />} />
          <Route path="actions" element={<Actions />} />
          <Route path="model" element={<ModelInformation />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="account" element={<AccountPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
