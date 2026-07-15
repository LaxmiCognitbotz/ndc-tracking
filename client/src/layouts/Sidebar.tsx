import { Link, useLocation } from "react-router";
import { LayoutDashboard, BarChart3, ChevronLeft, ChevronRight, FileText, Mail, Settings } from "lucide-react";
import imgLogo from "../assets/images/image.png";
import faviconLogo from "../assets/adani-favicon.png";
import { useSidebar } from "../context/SidebarContext";
import { useAuth } from "../context/AuthContext";

export function Sidebar() {
  const location = useLocation();
  const { isCollapsed, toggleSidebar } = useSidebar();
  const { user, ssoEnabled } = useAuth();

  const isActive = (path: string) => location.pathname === path;

  const menuItems = [
    {
      path: "/ndc-reporting/overview",
      label: "Overview Dashboard",
      icon: LayoutDashboard,
    },
    {
      path: "/ndc-reporting/analytics",
      label: "Analytics Dashboard",
      icon: BarChart3,
    },
    {
      path: "/ndc-reporting/fnf",
      label: "F&F Management",
      icon: FileText,
    },
    {
      path: "/ndc-reporting/email-config",
      label: "Email Recipients",
      icon: Mail,
    },
    {
      path: "/ndc-reporting/rm-email-configuration",
      label: "RM Email Master",
      icon: Settings,
    },
  ];

  return (
    <div
      className={`h-screen bg-sidebar border-r border-sidebar-border flex flex-col fixed left-0 top-0 transition-all duration-300 ${
        isCollapsed ? "w-20" : "w-64"
      }`}
    >
      <div className={`p-6 border-b border-sidebar-border flex items-center ${isCollapsed ? "justify-center" : "justify-between"}`}>
        {!isCollapsed && (
          <div className="flex items-center gap-3">
            <img src={imgLogo} alt="Adani" className="h-10 w-auto" />
            <span className="text-lg font-bold text-sidebar-foreground whitespace-nowrap">HR NDC System</span>
          </div>
        )}
        {isCollapsed && (
          <img src={faviconLogo} alt="Adani" className="h-8 w-auto" />
        )}
      </div>

      <div className="flex-1 px-3 py-6 space-y-1 overflow-y-auto">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.path);

          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-4 py-3 rounded-[4px] transition-all duration-200 ${
                active
                  ? "bg-sidebar-primary text-sidebar-primary-foreground"
                  : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              } ${isCollapsed ? "justify-center" : ""}`}
              title={isCollapsed ? item.label : ""}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              {!isCollapsed && <span className="font-medium whitespace-nowrap">{item.label}</span>}
            </Link>
          );
        })}
      </div>

      {user && ssoEnabled && !isCollapsed && (
        <div className="p-4 border-t border-sidebar-border flex flex-col gap-1 bg-sidebar-accent/20">
          <div className="flex flex-col px-1">
            <span className="text-sm font-semibold text-sidebar-foreground truncate" title={user.name}>{user.name}</span>
            <span className="text-xs text-sidebar-foreground/60 truncate" title={user.email}>{user.email}</span>
            <span className="text-[10px] uppercase font-bold text-teal-400 mt-1">
              {user.role === "super_admin" ? "Super Admin" : "Admin"}
            </span>
          </div>
        </div>
      )}

      <div className="p-4 border-t border-sidebar-border">
        <button
          onClick={toggleSidebar}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-[4px] bg-sidebar-accent hover:bg-sidebar-accent/80 text-sidebar-accent-foreground transition-colors"
          title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
        >
          {isCollapsed ? (
            <ChevronRight className="w-5 h-5" />
          ) : (
            <>
              <ChevronLeft className="w-5 h-5" />
              <span className="text-sm font-medium">Collapse</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
