import { Navigate, useLocation, useParams } from 'react-router-dom';

/**
 * Redireciona uma rota antiga preservando a query atual e somando parâmetros
 * do novo destino (ex.: `/regime?symbol=AAPL` → `/analise?tab=regime&symbol=AAPL`).
 */
export function RedirectTo({ to, params }: { to: string; params?: Record<string, string> }) {
  const location = useLocation();
  const routeParams = useParams();
  const search = new URLSearchParams(location.search);
  for (const [k, v] of Object.entries(params ?? {})) search.set(k, v);
  let path = to;
  for (const [k, v] of Object.entries(routeParams)) {
    if (v) path = path.replace(`:${k}`, encodeURIComponent(v));
  }
  const qs = search.toString();
  return <Navigate to={`${path}${qs ? `?${qs}` : ''}${location.hash}`} replace />;
}
