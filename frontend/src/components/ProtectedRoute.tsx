import { Navigate, Outlet, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useAuth } from '../context/AuthContext';
import { CenteredMessage } from './AuthLayout';

export function PublicOnlyRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <CenteredMessage role="status" title="Carregando…" />;
  }
  if (user) {
    return <Navigate to="/ferramenta" replace />;
  }
  return <>{children}</>;
}

export function ProtectedRoute() {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <CenteredMessage role="status" title="Carregando…" />;
  }
  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }
  return <Outlet />;
}

export function AdminRoute() {
  const { user, loading } = useAuth();

  if (loading) {
    return <CenteredMessage role="status" title="Carregando…" />;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (!user.is_admin) {
    return <Navigate to="/ferramenta" replace />;
  }
  return <Outlet />;
}
