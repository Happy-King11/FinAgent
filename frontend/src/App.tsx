import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { AuditPage } from "./pages/AuditPage";
import { ConsultPage } from "./pages/ConsultPage";
import { KnowledgePage } from "./pages/KnowledgePage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { ProductsPage } from "./pages/ProductsPage";
import { ProfilePage } from "./pages/ProfilePage";
import { SettingsPage } from "./pages/SettingsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/consult" replace />} />
        <Route path="consult" element={<ConsultPage />} />
        <Route path="knowledge" element={<KnowledgePage />} />
        <Route path="products" element={<ProductsPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="portfolio" element={<PortfolioPage />} />
        <Route path="audit" element={<AuditPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/consult" replace />} />
      </Route>
    </Routes>
  );
}
