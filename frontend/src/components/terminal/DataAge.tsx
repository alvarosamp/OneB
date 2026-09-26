import { AlertTriangle, RefreshCw } from 'lucide-react';
import { formatAge, minutesSince } from '../../lib/format';
import { useNow } from '../../hooks/useNow';
import { ICON_SM } from '../ui';
import styles from './DataAge.module.css';

interface DataAgeProps {
  /** Momento do dado (preferir o timestamp da fonte, não o da requisição). */
  at: string | Date | null | undefined;
  /** Minutos a partir dos quais o dado é considerado atrasado (amarelo). */
  staleAfterMin?: number;
  /** Falha na última atualização, mantendo o dado anterior. */
  refreshError?: string | null;
  refreshing?: boolean;
  prefix?: string;
}

/** "atualizado há 3 min" — em amarelo quando atrasado ou quando a última atualização falhou. */
export function DataAge({ at, staleAfterMin = 30, refreshError, refreshing, prefix = 'atualizado' }: DataAgeProps) {
  const now = useNow(30_000);
  const minutes = minutesSince(at ?? null, now);
  const stale = minutes !== null && minutes > staleAfterMin;
  if (refreshError) {
    return (
      <span className={[styles.age, styles.failed].join(' ')} title={refreshError}>
        <AlertTriangle {...ICON_SM} aria-hidden="true" />
        falha ao atualizar (último dado {formatAge(at ?? null, now)})
      </span>
    );
  }
  if (minutes === null) return <span className={styles.age}>sem horário</span>;
  const iso = at instanceof Date ? at.toISOString() : at ?? undefined;
  return (
    <span className={[styles.age, stale ? styles.stale : ''].join(' ')}>
      {stale && <AlertTriangle {...ICON_SM} aria-hidden="true" />}
      {refreshing && <RefreshCw {...ICON_SM} className="spin" aria-hidden="true" />}
      <time dateTime={iso}>
        {prefix} {formatAge(at ?? null, now)}
      </time>
      {stale && <span className="sr-only">(dado atrasado)</span>}
    </span>
  );
}
