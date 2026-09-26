import { clearAccessToken, getAccessToken, setAccessToken } from './authStore';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/** O backend exige este header nas rotas autenticadas por cookie (/refresh e /logout):
 * um site atacante não consegue definir header customizado num request cross-site, então
 * isso — somado a SameSite=strict — fecha o vetor de CSRF que o cookie reintroduziria. */
const REFRESH_HEADERS = { 'X-Refresh-Request': '1' };

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** Fired whenever the session is definitively gone so the app can redirect to /login. */
type UnauthorizedListener = () => void;
let onUnauthorized: UnauthorizedListener | null = null;
export function setUnauthorizedHandler(fn: UnauthorizedListener | null) {
  onUnauthorized = fn;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** Login/cadastro/refresh: um 401 aqui é credencial inválida, não sessão expirada —
   * não tenta renovar nem dispara o redirect de sessão. */
  skipAuth?: boolean;
}

async function rawFetch(path: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(
      0,
      'Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.',
    );
  }
}

/** Uma renovação por vez: várias chamadas que tomam 401 ao mesmo tempo compartilham
 * a mesma promessa em vez de rotacionarem o refresh token em paralelo (o que dispararia
 * a detecção de reuso no backend e derrubaria a sessão inteira). */
let refreshInFlight: Promise<boolean> | null = null;

export async function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await rawFetch('/api/auth/refresh', {
          method: 'POST',
          headers: REFRESH_HEADERS,
          credentials: 'include',
        });
        if (!res.ok) {
          clearAccessToken();
          return false;
        }
        const data = (await res.json()) as { access_token: string };
        setAccessToken(data.access_token);
        return true;
      } catch {
        clearAccessToken();
        return false;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

async function parseError(res: Response, fallback: string): Promise<string> {
  try {
    const data = await res.json();
    return data.detail ?? fallback;
  } catch {
    return fallback;
  }
}

async function request<T>(path: string, options: RequestOptions = {}, isRetry = false): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = getAccessToken();
  if (token && !options.skipAuth) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await rawFetch(path, {
    method: options.method ?? 'GET',
    headers,
    // O cookie de refresh é httpOnly e cross-origin (front e API em portas distintas):
    // sem 'include' o navegador não o envia nem o guarda.
    credentials: 'include',
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (res.status === 401) {
    if (options.skipAuth) {
      throw new ApiError(401, await parseError(res, 'Usuário ou senha inválidos.'));
    }
    // Access token expirou (dura minutos): tenta renovar em silêncio uma única vez
    // antes de considerar a sessão perdida.
    if (!isRetry && (await refreshSession())) {
      return request<T>(path, options, true);
    }
    clearAccessToken();
    onUnauthorized?.();
    throw new ApiError(401, 'Sessão expirada — faça login novamente.');
  }

  if (!res.ok) {
    throw new ApiError(res.status, await parseError(res, res.statusText));
  }

  if (res.status === 204) {
    return undefined as T;
  }
  try {
    return (await res.json()) as T;
  } catch {
    throw new ApiError(res.status, 'O servidor retornou uma resposta inválida. Tente novamente.');
  }
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'PUT', body }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};

/** Encerra a sessão no servidor (revoga a família de refresh tokens e apaga o cookie). */
export async function logoutRequest(): Promise<void> {
  clearAccessToken();
  await rawFetch('/api/auth/logout', {
    method: 'POST',
    headers: REFRESH_HEADERS,
    credentials: 'include',
  }).catch(() => undefined);
}

/** For downloads (PDF) — precisa do header Authorization, então um <a href> puro não serve. */
export async function fetchBlob(path: string, isRetry = false): Promise<Blob> {
  const token = getAccessToken();
  const res = await rawFetch(path, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    credentials: 'include',
  });

  if (res.status === 401 && !isRetry && (await refreshSession())) {
    return fetchBlob(path, true);
  }
  if (!res.ok) {
    throw new ApiError(res.status, await parseError(res, res.statusText));
  }
  return res.blob();
}

export { API_URL };
