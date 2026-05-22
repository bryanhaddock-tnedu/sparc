import { Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { FiscalYearProvider } from "./lib/fiscalYear";
import { AdminDataPage } from "./pages/AdminDataPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EstimationSettingsPage } from "./pages/EstimationSettingsPage";
import { IntegrationsPage } from "./pages/IntegrationsPage";
import { ProductDetailPage } from "./pages/ProductDetailPage";
import { ProductSettingsPage } from "./pages/ProductSettingsPage";
import { TeamManagementPage } from "./pages/TeamManagementPage";
import { TeamMemberDetailPage } from "./pages/TeamMemberDetailPage";

export default function App() {
  return (
    <FiscalYearProvider>
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
    </FiscalYearProvider>
  );
}
