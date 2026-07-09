import { createContext, type PropsWithChildren, useContext, useEffect, useMemo, useState } from "react";

import { api } from "./api";
import type { AuthStatus } from "../types/api";

interface AuthContextValue {
  status: AuthStatus | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .authStatus()
      .then(setStatus)
      .catch(() => setStatus({ auth_enabled: true, authenticated: false, username: null, user: null, capabilities: {} }))
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      loading,
      login: async (username: string, password: string) => {
        setStatus(await api.login(username, password));
      },
      logout: async () => {
        setStatus(await api.logout());
      },
    }),
    [loading, status],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
