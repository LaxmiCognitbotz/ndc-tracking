import { BrowserRouter, Routes, Route, Navigate } from "react-router";
import { Overview } from "./features/overview/Overview";
import { Analytics } from "./features/analytics/Analytics";
import { FNFManagement } from "./features/fnf/FNFManagement";
import { EmailConfig } from "./features/email-config/EmailConfig";
import { Sidebar } from "./layouts/Sidebar";
import { SidebarProvider, useSidebar } from "./context/SidebarContext";

function AppContent() {
  const { isCollapsed } = useSidebar();

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <div
        className={`transition-all duration-300 ${isCollapsed ? "ml-20" : "ml-64"}`}
      >
        <Routes>
          <Route path="/" element={<Navigate to="/ndc-reporting/overview" replace />} />
          <Route path="/ndc-reporting/overview" element={<Overview />} />
          <Route path="/ndc-reporting/analytics" element={<Analytics />} />
          <Route path="/ndc-reporting/fnf" element={<FNFManagement />} />
          <Route path="/ndc-reporting/email-config" element={<EmailConfig />} />
        </Routes>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <SidebarProvider>
        <AppContent />
      </SidebarProvider>
    </BrowserRouter>
  );
}
