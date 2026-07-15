import { ReactNode } from "react";
import { Navigate } from "react-router";
import { useAuth } from "../../context/AuthContext";
import { LoadingScreen } from "./LoadingScreen";

interface ProtectedRouteProps {
  children: ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { user, ssoEnabled, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <LoadingScreen />
      </div>
    );
  }

  // If SSO is disabled, allow immediate access to the full application
  if (!ssoEnabled) {
    return <>{children}</>;
  }

  // If no user session is active, show the loading screen while redirection takes place
  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <LoadingScreen />
      </div>
    );
  }

  // If session is active but pending approval
  if (user.status === "pending") {
    return <Navigate to="/pending" replace />;
  }

  // If session is active but access has been rejected
  if (user.status === "rejected") {
    return <Navigate to="/access-denied" replace />;
  }

  // User is approved and authenticated
  return <>{children}</>;
}
