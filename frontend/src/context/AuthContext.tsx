import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, logoutRequest, refreshSession, setUnauthorizedHandler } from '../api/client';
import { setAccessToken } from '../api/authStore';
import type { User } from '../types';

interface LoginResponse {
  access_token: string;
  user: User;
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  cadastro: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    setUser(null);
    // O refresh token é httpOnly — só o servidor consegue revogá-lo. O estado local já
    // foi limpo acima, então a UI reage na hora mesmo que a chamada falhe.
    void logoutRequest();
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
    return () => setUnauthorizedHandler(null);
  }, []);

  useEffect(() => {
    // O access token vive só em memória e morre no reload. Quem sobrevive é o cookie de
    // refresh (httpOnly), então a sessão é reconstruída pedindo um access token novo.
    let cancelled = false;
    (async () => {
      const renewed = await refreshSession();
      if (cancelled) return;
      if (!renewed) {
        setLoading(false);
        return;
      }
      try {
        const me = await api.get<User>('/api/auth/me');
        if (!cancelled) setUser(me);
      } catch {
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const data = await api.post<LoginResponse>('/api/auth/login', { username, password }, { skipAuth: true });
    setAccessToken(data.access_token);
    setUser(data.user);
  }, []);

  const cadastro = useCallback(async (username: string, password: string) => {
    const data = await api.post<LoginResponse>('/api/auth/cadastro', { username, password }, { skipAuth: true });
    setAccessToken(data.access_token);
    setUser(data.user);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, cadastro, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth precisa estar dentro de <AuthProvider>');
  return ctx;
}
