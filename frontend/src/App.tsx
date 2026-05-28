import { Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";

import { Layout } from "./components/Layout";
import { LoadingBlock } from "./components/StateBlocks";
import { AuthProvider, useAuth } from "./lib/auth";
import { FiscalYearProvider } from "./lib/fiscalYear";
import { AdminDataPage } from "./pages/AdminDataPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EstimationSettingsPage } from "./pages/EstimationSettingsPage";
import { IntegrationsPage } from "./pages/IntegrationsPage";
import { LoginPage } from "./pages/LoginPage";
import { ProductDetailPage } from "./pages/ProductDetailPage";
import { ProductSettingsPage } from "./pages/ProductSettingsPage";
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
              <Route path="/products/:productId" element={<ProductDetailPage />} />
              <Route path="/team-members/:teamMemberId" element={<TeamMemberDetailPage />} />
              <Route path="/team" element={<TeamManagementPage />} />
              <Route path="/integrations" element={<IntegrationsPage />} />
              <Route path="/admin-data" element={<AdminDataPage />} />
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
