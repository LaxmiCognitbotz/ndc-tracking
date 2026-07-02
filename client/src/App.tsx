import { createBrowserRouter, RouterProvider, Navigate, Outlet } from "react-router";
import { Overview } from "./features/overview/Overview";
import { Analytics } from "./features/analytics/Analytics";
import { FNFManagement } from "./features/fnf/FNFManagement";
import { EmailConfig } from "./features/email-config/EmailConfig";
import { RMEmailConfigurationPage } from "./features/rm-email-configuration/RMEmailConfigurationPage";
import { Sidebar } from "./layouts/Sidebar";
import { SidebarProvider, useSidebar } from "./context/SidebarContext";
import { Toaster } from "sonner";
import { GlobalErrorBoundary } from "./components/common/GlobalErrorBoundary";

function Layout() {
  const { isCollapsed } = useSidebar();

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <div
        className={`transition-all duration-300 ${isCollapsed ? "ml-20" : "ml-64"}`}
      >
        <Outlet />
      </div>
      <Toaster position="bottom-right" richColors />
    </div>
  );
}

const router = createBrowserRouter(
  [
    {
      element: (
        <SidebarProvider>
          <Layout />
        </SidebarProvider>
      ),
      children: [
        { index: true, element: <Navigate to="ndc-reporting/overview" replace /> },
        { path: "ndc-reporting/overview", element: <Overview /> },
        { path: "ndc-reporting/analytics", element: <Analytics /> },
        { path: "ndc-reporting/fnf", element: <FNFManagement /> },
        { path: "ndc-reporting/email-config", element: <EmailConfig /> },
        { path: "ndc-reporting/rm-email-configuration", element: <RMEmailConfigurationPage /> },
      ],
    },
  ],
  { basename: "/ndc" }
);

export default function App() {
  return (
    <GlobalErrorBoundary>
      <RouterProvider router={router} />
    </GlobalErrorBoundary>
  );
}
