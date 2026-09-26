import type { ReactNode } from 'react';
import { formatSignedPct } from '../../lib/format';
import styles from './Stat.module.css';

interface StatProps {
  label: ReactNode;
  value: ReactNode;
  /** Variação percentual; colorida por sinal (verde/vermelho). */
  changePct?: number | null;
  sub?: ReactNode;
  size?: 'md' | 'lg';
  align?: 'left' | 'right';
}

export function Stat({ label, value, changePct, sub, size = 'md', align = 'left' }: StatProps) {
  return (
    <div className={[styles.stat, size === 'lg' ? styles.lg : '', align === 'right' ? styles.right : ''].join(' ')}>
      <span className={styles.label}>{label}</span>
      <span className={styles.value}>{value}</span>
      {(changePct !== undefined || sub) && (
        <span className={styles.sub}>
          {changePct !== undefined && <ChangeText value={changePct} />}
          {sub}
        </span>
      )}
    </div>
  );
}

/** Variação com sinal e cor semântica. `null` vira "sem dado", nunca 0. */
export function ChangeText({ value, className }: { value: number | null | undefined; className?: string }) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return <span className={['muted', className ?? ''].join(' ')}>sem dado</span>;
  }
  const tone = value > 0 ? 'up' : value < 0 ? 'down' : 'muted';
  return <span className={['num', tone, className ?? ''].join(' ')}>{formatSignedPct(value)}</span>;
}
