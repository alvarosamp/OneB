import { useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';

/** Aba sincronizada com a query string (`?tab=`), para links diretos e redirects. */
export function useQueryTab<V extends string>(values: readonly V[], fallback: V, key = 'tab'): [V, (v: V) => void] {
  const [params, setParams] = useSearchParams();
  const raw = params.get(key);
  const value = (values as readonly string[]).includes(raw ?? '') ? (raw as V) : fallback;
  const setValue = useCallback(
    (next: V) => {
      setParams(
        (prev) => {
          const p = new URLSearchParams(prev);
          p.set(key, next);
          return p;
        },
        { replace: true },
      );
    },
    [key, setParams],
  );
  return [value, setValue];
}
