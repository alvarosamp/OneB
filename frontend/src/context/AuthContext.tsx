import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, clearToken, getToken, setToken as persistToken, setUnauthorizedHandler } from '../api/client';
import type { User } from '../types';

interface LoginResponse {
  access_token: string;
  user: User;
}

export interface CadastroData {
  username: string;
  email: string;
  password: string;
  acceptTerms: boolean;
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  cadastro: (data: CadastroData) => Promise<void>;
  /** Recarrega o usuário (plano, Telegram) depois de pagar ou vincular. */
  refreshUser: () => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
    return () => setUnauthorizedHandler(null);
  }, []);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .get<User>('/api/auth/me')
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const data = await api.post<LoginResponse>('/api/auth/login', { username, password }, { skipAuth: true });
    persistToken(data.access_token);
    setUser(data.user);
  }, []);

  const cadastro = useCallback(async ({ username, email, password, acceptTerms }: CadastroData) => {
    const data = await api.post<LoginResponse>(
      '/api/auth/cadastro',
      { username, email, password, accept_terms: acceptTerms },
      { skipAuth: true },
    );
    persistToken(data.access_token);
    setUser(data.user);
  }, []);

  const refreshUser = useCallback(async () => {
    setUser(await api.get<User>('/api/auth/me'));
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, cadastro, refreshUser, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth precisa estar dentro de <AuthProvider>');
  return ctx;
}
