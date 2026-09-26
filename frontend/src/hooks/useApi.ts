import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../api/client';

export type ApiStatus = 'loading' | 'error' | 'empty' | 'ready';

export interface ApiState<T> {
  data: T | null;
  status: ApiStatus;
  /** Mensagem da última falha. Pode existir junto de `data` (dado antigo mantido). */
  error: string | null;
  /** Código HTTP da última falha (0 = sem conexão). */
  errorStatus: number | null;
  lastUpdated: Date | null;
  /** true enquanto uma nova busca roda com dado já exibido. */
  refreshing: boolean;
  /** Busca de novo, mostrando skeleton se não houver dado. */
  retry: () => void;
  /** Substitui o dado localmente (ex.: após uma mutação). */
  mutate: (updater: T | ((prev: T | null) => T)) => void;
}

export interface UseApiOptions<T> {
  /** Intervalo de atualização em ms. Pausa quando a aba está oculta. */
  pollMs?: number;
  /** Define quando a resposta conta como "vazia". Padrão: null, [] ou objeto sem chaves. */
  isEmpty?: (data: T) => boolean;
  /** false impede a busca (ex.: símbolo ainda não escolhido). */
  enabled?: boolean;
}

interface CacheEntry {
  data: unknown;
  at: number;
}

// Cache em memória: ao voltar para uma tela, o último dado aparece na hora
// enquanto a busca nova acontece (stale-while-revalidate).
const cache = new Map<string, CacheEntry>();

export function clearApiCache() {
  cache.clear();
}

export function defaultIsEmpty(data: unknown): boolean {
  if (data === null || data === undefined) return true;
  if (Array.isArray(data)) return data.length === 0;
  if (typeof data === 'object') return Object.keys(data as object).length === 0;
  return false;
}

function messageFrom(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 0) return err.message;
    if (err.status === 404) return `Sem dados disponíveis (${err.message})`;
    if (err.status >= 500) return `O servidor falhou ao responder (${err.status}). ${err.message}`;
    return err.message;
  }
  return err instanceof Error ? err.message : 'Erro desconhecido ao buscar dados';
}

/**
 * Busca `path` na API e expõe os quatro estados de um bloco de dados.
 * Cada bloco usa seu próprio hook, então a falha de um não derruba os outros.
 */
export function useApi<T>(path: string | null, options: UseApiOptions<T> = {}): ApiState<T> {
  const { pollMs, enabled = true } = options;
  const isEmptyRef = useRef(options.isEmpty ?? defaultIsEmpty);
  isEmptyRef.current = options.isEmpty ?? defaultIsEmpty;

  const cached = path ? (cache.get(path) as CacheEntry | undefined) : undefined;
  const [data, setData] = useState<T | null>((cached?.data as T) ?? null);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(cached ? new Date(cached.at) : null);
  const [loading, setLoading] = useState<boolean>(!cached && enabled && !!path);
  const [refreshing, setRefreshing] = useState(false);
  const [nonce, setNonce] = useState(0);
  const dataRef = useRef<T | null>(data);
  dataRef.current = data;

  // Quando o caminho muda, começa do cache do novo caminho (ou vazio).
  const [prevPath, setPrevPath] = useState(path);
  if (prevPath !== path) {
    setPrevPath(path);
    const entry = path ? cache.get(path) : undefined;
    setData((entry?.data as T) ?? null);
    setLastUpdated(entry ? new Date(entry.at) : null);
    setError(null);
    setErrorStatus(null);
    setLoading(!entry && enabled && !!path);
  }

  useEffect(() => {
    if (!path || !enabled) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function run() {
      if (dataRef.current !== null) setRefreshing(true);
      else setLoading(true);
      try {
        const result = await api.get<T>(path!);
        if (cancelled) return;
        const now = Date.now();
        cache.set(path!, { data: result, at: now });
        setData(result);
        setError(null);
        setErrorStatus(null);
        setLastUpdated(new Date(now));
      } catch (err) {
        if (cancelled) return;
        setError(messageFrom(err));
        setErrorStatus(err instanceof ApiError ? err.status : null);
      } finally {
        if (!cancelled) {
          setLoading(false);
          setRefreshing(false);
          schedule();
        }
      }
    }

    function schedule() {
      if (!pollMs || cancelled) return;
      timer = setTimeout(() => {
        if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
          schedule();
          return;
        }
        void run();
      }, pollMs);
    }

    function onVisible() {
      if (document.visibilityState === 'visible' && pollMs) {
        if (timer) clearTimeout(timer);
        void run();
      }
    }

    void run();
    if (pollMs) document.addEventListener('visibilitychange', onVisible);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      if (pollMs) document.removeEventListener('visibilitychange', onVisible);
    };
  }, [path, pollMs, enabled, nonce]);

  const retry = useCallback(() => setNonce((n) => n + 1), []);

  const mutate = useCallback(
    (updater: T | ((prev: T | null) => T)) => {
      setData((prev) => {
        const next = typeof updater === 'function' ? (updater as (p: T | null) => T)(prev) : updater;
        if (path) cache.set(path, { data: next, at: Date.now() });
        return next;
      });
    },
    [path],
  );

  let status: ApiStatus;
  if (data !== null) status = isEmptyRef.current(data) ? 'empty' : 'ready';
  else if (loading) status = 'loading';
  // Nesta API, 404 em endpoint de dados significa "sem dados" (ex.: regime sem histórico).
  else if (error && errorStatus === 404) status = 'empty';
  else if (error) status = 'error';
  else if (!enabled || !path) status = 'empty';
  else status = 'loading';

  return { data, status, error, errorStatus, lastUpdated, refreshing, retry, mutate };
}
