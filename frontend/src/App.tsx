import { Navigate, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";

import { Layout } from "./components/Layout";
import { LoadingBlock } from "./components/StateBlocks";
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
              <Route path="/team-members/:teamMemberRef" element={<TeamMemberDetailPage />} />
              <Route path="/teams/:teamSlug" element={<TeamAnalyticsPage />} />
              <Route path="/team" element={<TeamManagementPage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/admin" element={<AdminPage />} />
              <Route path="/integrations" element={<Navigate to="/admin?tab=jira" replace />} />
              <Route path="/admin-data" element={<Navigate to="/admin?tab=data" replace />} />
              <Route path="/estimations" element={<EstimationSettingsPage />} />
            </Routes>
          </Layout>
        </AuthGate>
      </FiscalYearProvider>
    </AuthProvider>
  );
}

function AuthGate({ children }: { children: ReactNode }) {
  const { loading, status } = useAuth();
  if (loading) return <LoadingBlock />;
  if (status?.auth_enabled && !status.authenticated) return <LoginPage />;
  return children;
}
