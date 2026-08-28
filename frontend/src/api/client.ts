const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const TOKEN_KEY = 'oneb_market_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** Fired whenever a request comes back 401 so the app can redirect to /login. */
type UnauthorizedListener = () => void;
let onUnauthorized: UnauthorizedListener | null = null;
export function setUnauthorizedHandler(fn: UnauthorizedListener | null) {
  onUnauthorized = fn;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  skipAuth?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = getToken();
  if (token && !options.skipAuth) {
    headers.Authorization = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new ApiError(
      0,
      'Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.',
    );
  }

  if (res.status === 401) {
    if (options.skipAuth) {
      // Login/cadastro themselves returning 401 means wrong credentials, not
      // an expired session — surface the backend's real message instead of
      // a generic "not authenticated" that reads like an infra problem.
      let detail = 'Usuário ou senha inválidos.';
      try {
        const data = await res.json();
        detail = data.detail ?? detail;
      } catch {
        // response body wasn't JSON — keep the default message
      }
      throw new ApiError(401, detail);
    }
    clearToken();
    onUnauthorized?.();
    throw new ApiError(401, 'Sessão expirada — faça login novamente.');
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail ?? detail;
    } catch {
      // response body wasn't JSON — keep statusText
    }
    throw new ApiError(res.status, detail);
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

/** For downloads (PDF) — needs the Authorization header, so a plain <a href> won't work. */
export async function fetchBlob(path: string): Promise<Blob> {
  const token = getToken();
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  } catch {
    throw new ApiError(0, 'Não foi possível conectar ao servidor. Tente novamente.');
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail ?? detail;
    } catch {
      // Downloads may return an empty or non-JSON error response.
    }
    throw new ApiError(res.status, detail);
  }
  return res.blob();
}

export { API_URL };
