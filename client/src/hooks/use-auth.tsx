import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { apiRequest } from "@/lib/queryClient";
import type { AuthSession } from "@shared/schema";

type AuthContextValue = {
  session: AuthSession;
  loading: boolean;
  refreshSession: () => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const unauthenticatedSession: AuthSession = {
  authenticated: false,
  session_type: "session_cookie",
  setup_required: false,
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function fetchSession(): Promise<AuthSession> {
  const response = await fetch("/api/auth/session", { credentials: "include" });
  if (!response.ok) {
    throw new Error("Failed to fetch auth session");
  }
  return (await response.json()) as AuthSession;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession>(unauthenticatedSession);
  const [loading, setLoading] = useState(true);

  const refreshSession = async () => {
    try {
      const next = await fetchSession();
      setSession(next);
    } catch {
      setSession(unauthenticatedSession);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refreshSession();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      loading,
      refreshSession,
      login: async (username: string, password: string) => {
        await apiRequest("POST", "/api/auth/login", { username, password });
        await refreshSession();
      },
      logout: async () => {
        await apiRequest("POST", "/api/auth/logout");
        setSession(unauthenticatedSession);
      },
    }),
    [loading, session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
