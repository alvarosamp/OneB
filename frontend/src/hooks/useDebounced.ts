import { useEffect, useState } from 'react';

/** O valor só muda depois de `ms` sem alterações (ex.: não consultar o servidor a cada tecla). */
export function useDebounced<T>(value: T, ms = 400): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}
