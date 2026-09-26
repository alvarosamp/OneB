import { useEffect, useState } from 'react';

/** Relógio que re-renderiza a cada `intervalMs` (idade de dados, status de mercado). */
export function useNow(intervalMs = 30_000): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}
