import { useEffect, useState, type ChangeEvent } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, AlertTriangle } from 'lucide-react';
import { useApi } from '../../hooks/useApi';
import { chartPath, findTimeframe } from '../../lib/timeframes';
import { lastValue } from '../../lib/indicators';
import { simulate, type Direction } from '../../lib/simulator';
import { formatCurrency, formatNumber, isNum } from '../../lib/format';
import { assetHref } from '../../lib/watchlist';
import type { ChartData } from '../../types';
import { ChartPanel } from '../terminal/ChartPanel';
import { AsyncContent, EmptyState, ICON, Input, Select, Skeleton } from '../ui';
import styles from './Player.module.css';

/**
 * "Praticar no gráfico": a aula termina no mercado de verdade. Gráfico com
 * dado real do ativo da aula + simulador de plano (entrada, stop, alvo).
 */
export function Practice({ symbol, hint }: { symbol: string; hint: string }) {
  const tf = findTimeframe('5D');
  const chart = useApi<ChartData>(chartPath(symbol, tf), { isEmpty: (d) => d.close.length === 0 });
  const last = chart.data ? lastValue(chart.data.close) : null;

  return (
    <div className={styles.practice}>
      <p className={styles.reading}>{hint}</p>
      <AsyncContent
        state={chart}
        loading={<Skeleton height={300} />}
        empty={<EmptyState title={`Sem candles de ${symbol} agora`} description="O simulador abaixo continua disponível com valores manuais." />}
        errorTitle="Gráfico indisponível"
      >
        {(data) => <ChartPanel data={data} timeframe={tf} panels={['volume']} height={260} label={symbol} />}
      </AsyncContent>
      <p className={styles.meta}>
        Dado real de {symbol}. <Link to={assetHref(symbol)}>Abrir no terminal</Link>
      </p>
      <Simulator symbol={symbol} lastPrice={last} />
    </div>
  );
}

function Simulator({ symbol, lastPrice }: { symbol: string; lastPrice: number | null }) {
  const [direction, setDirection] = useState<Direction>('LONG');
  const [capital, setCapital] = useState(10000);
  const [riskPct, setRiskPct] = useState(1);
  const [entry, setEntry] = useState(100);
  const [stop, setStop] = useState(98);
  const [target, setTarget] = useState(106);
  const [seeded, setSeeded] = useState(false);

  // Parte do último preço real, com stop a 1% e alvo a 3% (2R… 3R), para o aluno ajustar.
  useEffect(() => {
    if (!seeded && isNum(lastPrice)) {
      const p = Number(lastPrice.toFixed(2));
      setEntry(p);
      setStop(Number((p * 0.99).toFixed(2)));
      setTarget(Number((p * 1.03).toFixed(2)));
      setSeeded(true);
    }
  }, [lastPrice, seeded]);

  const r = simulate({ direction, capital, riskPct, entry, stop, target });
  const num = (set: (n: number) => void) => (e: ChangeEvent<HTMLInputElement>) => set(Number(e.target.value));

  return (
    <section className={styles.sim} aria-label="Simulador de plano">
      <h3 className={styles.subTitle}>Simule o plano em {symbol}</h3>
      <div className={styles.simGrid}>
        <Select label="Direção" value={direction} onChange={(e) => setDirection(e.target.value as Direction)}>
          <option value="LONG">Alta (long)</option>
          <option value="SHORT">Baixa (short)</option>
        </Select>
        <Input label="Capital (US$)" type="number" min="100" value={capital} onChange={num(setCapital)} />
        <Input label="Risco (%)" type="number" min="0.1" step="0.1" value={riskPct} onChange={num(setRiskPct)} />
        <Input label="Entrada" type="number" step="0.01" value={entry} onChange={num(setEntry)} />
        <Input label="Stop" type="number" step="0.01" value={stop} onChange={num(setStop)} />
        <Input label="Alvo" type="number" step="0.01" value={target} onChange={num(setTarget)} />
      </div>
      <dl className={styles.simOut}>
        <div>
          <dt>Quantidade</dt>
          <dd className="num">{r.quantity}</dd>
        </div>
        <div>
          <dt>Risco planejado</dt>
          <dd className="num">{formatCurrency(r.plannedRisk)}</dd>
        </div>
        <div>
          <dt>Retorno potencial</dt>
          <dd className="num">{formatCurrency(r.plannedReward)}</dd>
        </div>
        <div>
          <dt>Risco/retorno</dt>
          <dd className="num">{formatNumber(r.rr, 2)}R</dd>
        </div>
      </dl>
      <ul className={styles.checks}>
        {r.checks.map((c) => (
          <li key={c.id} className={c.ok ? styles.checkOk : styles.checkWarn}>
            {c.ok ? <CheckCircle2 {...ICON} aria-hidden="true" /> : <AlertTriangle {...ICON} aria-hidden="true" />}
            {c.text}
          </li>
        ))}
      </ul>
    </section>
  );
}
