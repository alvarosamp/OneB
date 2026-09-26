import { useCallback, useRef, useState } from 'react';

export type ActionStatus = 'idle' | 'running' | 'error' | 'done';

/** Estado de uma ação disparada pelo usuário (POST, análise sob demanda). */
export function useAction<Args extends unknown[], R>(fn: (...args: Args) => Promise<R>) {
  const [status, setStatus] = useState<ActionStatus>('idle');
  const [data, setData] = useState<R | null>(null);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const run = useCallback(async (...args: Args) => {
    const id = ++seq.current;
    setStatus('running');
    setError(null);
    try {
      const result = await fnRef.current(...args);
      if (id === seq.current) {
        setData(result);
        setStatus('done');
      }
      return result;
    } catch (err) {
      if (id === seq.current) {
        setError(err instanceof Error ? err.message : 'Erro desconhecido');
        setStatus('error');
      }
      return null;
    }
  }, []);

  const reset = useCallback(() => {
    seq.current++;
    setStatus('idle');
    setData(null);
    setError(null);
  }, []);

  return { status, data, error, run, reset };
}
