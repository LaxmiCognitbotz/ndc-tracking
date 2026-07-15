import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import api from "../lib/axios";

export interface User {
  email: string;
  name: string;
  role: "super_admin" | "admin";
  status: "approved" | "pending" | "rejected";
}

interface AuthContextType {
  user: User | null;
  ssoEnabled: boolean;
  isSuperAdmin: boolean;
  isAdmin: boolean;
  isLoading: boolean;
  login: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ssoEnabled, setSsoEnabled] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Check login parameters from URL (OIDC Callback redirect)
  const checkUrlParams = () => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    const email = params.get("email");
    const role = params.get("role") as User["role"];
    const name = params.get("name");

    if (token && email && role) {
      localStorage.setItem("token", token);
      const newUser: User = {
        email,
        name: name || email.split("@")[0],
        role,
        status: "approved",
      };
      setUser(newUser);
      
      // Clean up URL parameters from browser address bar
      const cleanUrl = window.location.pathname;
      window.history.replaceState({}, document.title, cleanUrl);
      return true;
    }
    return false;
  };

  const loadAuth = async () => {
    try {
      // 1. Fetch SSO Enabled status from backend
      // Use skipGlobalToast to prevent error notifications if server is not fully initialized yet
      const configRes = await api.get<any>("api/auth/config", {
        skipGlobalToast: true,
      } as any);
      const isSso = !!(configRes.data?.data?.sso_enabled ?? configRes.data?.sso_enabled);
      setSsoEnabled(isSso);

      if (!isSso) {
        // Direct developer access bypass
        setUser({
          email: "dev@local.com",
          name: "Dev User",
          role: "super_admin",
          status: "approved",
        });
        setIsLoading(false);
        return;
      }

      // 2. Check if query parameters contain new token (SSO login redirection callback)
      const didLoginFromUrl = checkUrlParams();
      if (didLoginFromUrl) {
        setIsLoading(false);
        return;
      }

      // 3. Otherwise, check localStorage for existing session token
      const token = localStorage.getItem("token");
      const isAuthPage = window.location.pathname.endsWith("/pending") || window.location.pathname.endsWith("/access-denied");

      if (token) {
        try {
          const profileRes = await api.get<any>("api/auth/me", {
            skipGlobalToast: true,
          } as any);
          const profileData = profileRes.data?.data || profileRes.data;
          setUser(profileData);
        } catch (err: any) {
          // Token expired or invalid
          console.error("Profile fetch failed, logging out", err);
          localStorage.removeItem("token");
          setUser(null);
          if (!isAuthPage) {
            // Trigger auto login redirect
            setIsLoading(true);
            const loginRes = await api.get<any>("api/auth/login");
            const loginData = loginRes.data?.data || loginRes.data;
            if (loginData.url) {
              window.location.href = loginData.url;
              return;
            }
          }
        }
      } else {
        setUser(null);
        if (!isAuthPage) {
          // Trigger auto login redirect
          setIsLoading(true);
          const loginRes = await api.get<any>("api/auth/login");
          const loginData = loginRes.data?.data || loginRes.data;
          if (loginData.url) {
            window.location.href = loginData.url;
            return;
          }
        }
      }
    } catch (err) {
      console.error("Failed to load auth config or profile", err);
      // Fallback
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAuth();
  }, []);

  const login = async () => {
    try {
      setIsLoading(true);
      const loginRes = await api.get<any>("api/auth/login");
      const loginData = loginRes.data?.data || loginRes.data;
      if (loginData.url) {
        window.location.href = loginData.url;
      }
    } catch (err) {
      console.error("Failed to initiate login flow", err);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      setIsLoading(true);
      const token = localStorage.getItem("token");
      if (token) {
        try {
          const logoutRes = await api.post<any>("api/auth/logout");
          const logoutData = logoutRes.data?.data || logoutRes.data;
          if (logoutData.logout_url) {
            localStorage.removeItem("token");
            setUser(null);
            window.location.href = logoutData.logout_url;
            return;
          }
        } catch (err) {
          console.error("Logout request to backend failed", err);
        }
      }
    } finally {
      localStorage.removeItem("token");
      setUser(null);
      setIsLoading(false);
    }
  };

  const isSuperAdmin = user?.role === "super_admin";
  const isAdmin = user?.role === "admin" || user?.role === "super_admin";

  return (
    <AuthContext.Provider
      value={{
        user,
        ssoEnabled,
        isSuperAdmin,
        isAdmin,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
