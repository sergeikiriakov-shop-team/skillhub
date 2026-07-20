// Auth state for the SPA: reads /api/auth/me (cookie session), exposes login/logout.
// Login is a full-page navigation (a fetch can't follow the cross-origin 302 to the provider);
// logout is a POST that revokes the session, then we refetch /me.

import { createContext, useCallback, useContext, useMemo } from "react";
import type { ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { Me } from "./api";

interface AuthContextValue {
  me: Me | undefined;
  isLoading: boolean;
  isAuthenticated: boolean;
  readsRequireAuth: boolean;
  login: (next?: string) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const { data: me, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: api.me,
    staleTime: 60_000,
  });

  const login = useCallback((next?: string) => {
    let dest = next;
    if (dest === undefined) {
      // Don't carry a previous ?login_error into the return URL, or a successful re-login would land
      // back on the error banner.
      const params = new URLSearchParams(window.location.search);
      params.delete("login_error");
      const qs = params.toString();
      dest = window.location.pathname + (qs ? `?${qs}` : "");
    }
    window.location.href = `/api/auth/login?next=${encodeURIComponent(dest)}`;
  }, []);

  const logout = useCallback(async () => {
    await api.logout();
    await qc.invalidateQueries({ queryKey: ["me"] });
  }, [qc]);

  const value = useMemo<AuthContextValue>(
    () => ({
      me,
      isLoading,
      isAuthenticated: !!me?.authenticated,
      readsRequireAuth: !!me?.reads_require_auth,
      login,
      logout,
    }),
    [me, isLoading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
