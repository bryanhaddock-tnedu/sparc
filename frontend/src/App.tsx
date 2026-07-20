import { Navigate, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";

import { Layout } from "./components/Layout";
import { ErrorBlock, LoadingBlock } from "./components/StateBlocks";
import { AuthProvider, useAuth } from "./lib/auth";
import { FiscalYearProvider } from "./lib/fiscalYear";
import { AdminPage } from "./pages/AdminPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EstimationSettingsPage } from "./pages/EstimationSettingsPage";
import { LoginPage } from "./pages/LoginPage";
import { ProductDetailPage } from "./pages/ProductDetailPage";
import { ProductSettingsPage } from "./pages/ProductSettingsPage";
import { ReportsPage } from "./pages/ReportsPage";
import { TeamAnalyticsPage } from "./pages/TeamAnalyticsPage";
import { TeamManagementPage } from "./pages/TeamManagementPage";
import { TeamMemberDetailPage } from "./pages/TeamMemberDetailPage";
import type { AuthCapabilities } from "./types/api";

export default function App() {
  return (
    <AuthProvider>
      <FiscalYearProvider>
        <AuthGate>
          <Layout>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/products/settings" element={<ProductSettingsPage />} />
              <Route path="/products/:productRef" element={<ProductDetailPage />} />
              <Route
                path="/team-members/:teamMemberRef"
                element={
                  <RequireCapability capability="can_view_team_member_profiles" message="Team Member profiles are not available for your role.">
                    <TeamMemberDetailPage />
                  </RequireCapability>
                }
              />
              <Route
                path="/teams/:teamSlug"
                element={
                  <RequireCapability capability="can_view_named_people" message="Team analytics are not available for your role.">
                    <TeamAnalyticsPage />
                  </RequireCapability>
                }
              />
              <Route
                path="/team"
                element={
                  <RequireCapability capability="can_view_named_people" message="Team Management is not available for your role.">
                    <TeamManagementPage />
                  </RequireCapability>
                }
              />
              <Route
                path="/reports"
                element={
                  <RequireCapability capability="can_view_reports" message="Reports are not available for your role.">
                    <ReportsPage />
                  </RequireCapability>
                }
              />
              <Route
                path="/admin"
                element={
                  <RequireCapability capability="can_admin" message="Admin tools are not available for your role.">
                    <AdminPage />
                  </RequireCapability>
                }
              />
              <Route path="/integrations" element={<Navigate to="/admin?tab=jira" replace />} />
              <Route path="/admin-data" element={<Navigate to="/admin?tab=data" replace />} />
              <Route
                path="/estimations"
                element={
                  <RequireCapability capability="can_admin" message="Estimation settings are not available for your role.">
                    <EstimationSettingsPage />
                  </RequireCapability>
                }
              />
            </Routes>
          </Layout>
        </AuthGate>
      </FiscalYearProvider>
    </AuthProvider>
  );
}

function RequireCapability({
  capability,
  children,
  message,
}: {
  capability: keyof AuthCapabilities;
  children: ReactNode;
  message: string;
}) {
  const { status } = useAuth();
  if (status?.capabilities[capability] === true) return children;
  return <ErrorBlock message={message} />;
}

function AuthGate({ children }: { children: ReactNode }) {
  const { loading, status } = useAuth();
  if (loading) return <LoadingBlock />;
  if (status?.auth_enabled && !status.authenticated) return <LoginPage />;
  return children;
}
