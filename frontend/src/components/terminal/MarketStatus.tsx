import { useEffect, useRef, useState } from 'react';
import { describeStatus, getMarketStatus, MARKETS, userTimeZone, type MarketStatus as Status } from '../../lib/marketHours';
import { useNow } from '../../hooks/useNow';
import styles from './MarketStatus.module.css';

const PHASE_LABEL = { open: 'aberto', closed: 'fechado', break: 'em pausa' } as const;

/**
 * Status real dos mercados (NASDAQ, COMEX, B3), recalculado a cada minuto.
 * O botão mostra a NASDAQ; o painel lista os três.
 */
export function MarketStatus() {
  const now = useNow(60_000);
  const tz = userTimeZone();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const statuses: Status[] = MARKETS.map((m) => getMarketStatus(m.id, now));
  const nasdaq = statuses[0];

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  const dotCls = (s: Status) => [styles.dot, s.phase === 'open' ? styles.open : s.phase === 'break' ? styles.break : ''].join(' ');

  return (
    <div className={styles.wrap} ref={ref} onKeyDown={(e) => e.key === 'Escape' && setOpen(false)}>
      <button type="button" className={styles.trigger} aria-expanded={open} aria-haspopup="dialog" onClick={() => setOpen((v) => !v)}>
        <span className={dotCls(nasdaq)} aria-hidden="true" />
        <span className={styles.name}>NASDAQ</span>
        <span className={styles.text}>{describeStatus(nasdaq, now, tz)}</span>
        <span className="sr-only">
          {PHASE_LABEL[nasdaq.phase]}. Ver status dos mercados
        </span>
      </button>
      {open && (
        <div className={styles.panel} role="dialog" aria-label="Status dos mercados">
          <ul className={styles.list}>
            {statuses.map((s) => (
              <li key={s.market.id} className={styles.row}>
                <span className={dotCls(s)} aria-hidden="true" />
                <span>
                  <span className={styles.name}>{s.market.name}</span>
                  <span className={styles.detail}>{describeStatus(s, now, tz)}</span>
                </span>
              </li>
            ))}
          </ul>
          <p className={styles.note}>Calculado pelo relógio do seu dispositivo. Feriados cobertos: NYSE/Nasdaq 2026–2027 e B3 2026. A COMEX não considera feriados da CME.</p>
        </div>
      )}
    </div>
  );
}
