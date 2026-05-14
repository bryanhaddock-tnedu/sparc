import { Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { IntegrationsPage } from "./pages/IntegrationsPage";
import { ProductDetailPage } from "./pages/ProductDetailPage";
import { TeamManagementPage } from "./pages/TeamManagementPage";
import { TeamMemberDetailPage } from "./pages/TeamMemberDetailPage";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/products/:productId" element={<ProductDetailPage />} />
        <Route path="/team-members/:teamMemberId" element={<TeamMemberDetailPage />} />
        <Route path="/team" element={<TeamManagementPage />} />
        <Route path="/integrations" element={<IntegrationsPage />} />
      </Routes>
    </Layout>
  );
}
