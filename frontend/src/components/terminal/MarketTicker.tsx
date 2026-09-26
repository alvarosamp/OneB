import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle } from 'lucide-react';
import { useApi } from '../../hooks/useApi';
import { TICKER, type TickerInstrument } from '../../content/instruments';
import { formatCurrency, formatNumber, formatAge, isNum, minutesSince } from '../../lib/format';
import { chartPath } from '../../lib/timeframes';
import type { ChartData, FxQuote, MacroOverview } from '../../types';
import { ChangeText, ErrorState, ICON_SM, Skeleton, Tooltip } from '../ui';
import { Sparkline } from './Sparkline';
import styles from './MarketTicker.module.css';

interface Quote {
  price: number | null;
  changePct: number | null;
  at: string | null;
}

function formatQuote(inst: TickerInstrument, price: number | null) {
  if (!isNum(price)) return null;
  switch (inst.kind) {
    case 'usd':
      return formatCurrency(price, 'USD');
    case 'brl':
      return formatCurrency(price, 'BRL', 4);
    case 'yield':
      return `${formatNumber(price, 2)}%`;
    default:
      return formatNumber(price, 2);
  }
}

const SPARK_TF = { period: '5d', interval: '1h' };

function TickerItem({ inst, quote }: { inst: TickerInstrument; quote: Quote }) {
  const spark = useApi<ChartData>(inst.spark ? chartPath(inst.spark, SPARK_TF) : null, { pollMs: 5 * 60_000 });
  const prev = useRef<number | null>(quote.price);
  const [flash, setFlash] = useState<'up' | 'down' | null>(null);

  useEffect(() => {
    if (isNum(prev.current) && isNum(quote.price) && quote.price !== prev.current) {
      setFlash(quote.price > prev.current ? 'up' : 'down');
      const id = setTimeout(() => setFlash(null), 900);
      prev.current = quote.price;
      return () => clearTimeout(id);
    }
    prev.current = quote.price;
  }, [quote.price]);

  const age = minutesSince(quote.at);
  const stale = age !== null && age > inst.staleAfterMin;
  const closes = spark.data?.close ?? [];
  const first = closes.find((v) => v !== null) ?? null;
  const last = [...closes].reverse().find((v) => v !== null) ?? null;
  const tone = isNum(first) && isNum(last) ? (last > first ? 'positive' : last < first ? 'negative' : 'neutral') : 'neutral';
  const price = formatQuote(inst, quote.price);

  const body = (
    <>
      <span className={styles.label}>
        {inst.label}
        {stale && (
          <Tooltip content={`Dado atrasado: ${formatAge(quote.at)}.${inst.note ? ` ${inst.note}` : ''}`}>
            <AlertTriangle {...ICON_SM} aria-label="Dado atrasado" tabIndex={0} />
          </Tooltip>
        )}
      </span>
      <span className={[styles.price, flash === 'up' ? styles.flashUp : flash === 'down' ? styles.flashDown : ''].join(' ')}>
        {price ?? <span className={styles.empty}>sem cotação</span>}
      </span>
      <span className={styles.change}>{price ? <ChangeText value={quote.changePct} /> : null}</span>
      <span className={styles.spark}>
        <Sparkline values={closes.slice(-60)} width={56} tone={tone} label={`${inst.label}, últimos 5 dias`} />
      </span>
    </>
  );

  const title = `${inst.name}${quote.at ? `, ${formatAge(quote.at)}` : ''}`;
  return inst.href ? (
    <Link to={inst.href} className={styles.item} title={title} aria-label={`${inst.label}: ${price ?? 'sem cotação'}. Abrir gráfico`}>
      {body}
    </Link>
  ) : (
    <div className={styles.item} title={title}>
      {body}
    </div>
  );
}

/** Faixa de instrumentos: preço, variação e sparkline de 5 dias. */
export function MarketTicker() {
  const macro = useApi<MacroOverview>('/api/regime/macro', { pollMs: 60_000, isEmpty: (d) => d.instruments.length === 0 });
  const fx = useApi<FxQuote>('/api/fx/usd-brl', { pollMs: 5 * 60_000 });

  if (macro.status === 'loading' && fx.status === 'loading') {
    return (
      <div className={styles.ticker} aria-busy="true" aria-label="Carregando cotações">
        {TICKER.map((t) => (
          <div key={t.id} className={styles.item}>
            <span className={styles.skeleton}>
              <Skeleton width={40} height={10} />
              <Skeleton width={90} height={18} />
              <Skeleton width={50} height={10} />
            </span>
          </div>
        ))}
      </div>
    );
  }

  if (macro.status === 'error' && fx.status === 'error') {
    return <ErrorState title="Cotações indisponíveis" error={macro.error} onRetry={() => (macro.retry(), fx.retry())} />;
  }

  const items: { inst: TickerInstrument; quote: Quote }[] = [];
  for (const inst of TICKER) {
    if (inst.source === 'fx') {
      if (fx.data) items.push({ inst, quote: { price: fx.data.rate, changePct: fx.data.change_pct, at: fx.data.updated_at } });
      continue;
    }
    const row = macro.data?.instruments.find((i) => i.key === inst.macroKey);
    // Instrumento sem fonte na API simplesmente não aparece.
    if (row) items.push({ inst, quote: { price: row.price, changePct: row.change_pct, at: row.taken_at } });
  }

  return (
    <section className={styles.ticker} aria-label="Cotações de referência">
      {items.map(({ inst, quote }) => (
        <TickerItem key={inst.id} inst={inst} quote={quote} />
      ))}
    </section>
  );
}
