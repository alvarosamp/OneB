import { useEffect, useMemo, useRef, useState } from 'react';
import { Pause, Play, RotateCcw, StepForward } from 'lucide-react';
import { useApi } from '../../hooks/useApi';
import { findTimeframe } from '../../lib/timeframes';
import { readJson, writeJson } from '../../lib/storage';
import { formatNumber } from '../../lib/format';
import {
  closePosition,
  equity,
  initLab,
  labStats,
  onBar,
  openPnl,
  openPosition,
  quote,
  sizeByRisk,
  type LabBar,
  type LabState,
  type Side,
} from '../../lib/tradingLab';
import type { ChartData, LabReplay, LabReplaySummary } from '../../types';
import { ChartPanel, type PriceLevel } from '../terminal/ChartPanel';
import { AsyncContent, Badge, Button, ChipGroup, EmptyState, ICON, Input, Select, Skeleton, Stat } from '../ui';
import styles from './TradingLab.module.css';

type Mode = 'replay' | 'live';

const START_BALANCE = 10_000;

/**
 * Laboratório da Academia: conta simulada de US$ 10.000 para treinar a execução
 * de um plano. Replay guiado de dias reais (como um vídeo, com pausas para decidir)
 * ou cotação ao vivo com atraso. Nenhuma ordem sai daqui.
 */
export function TradingLab({ initialMode = 'replay', replaySlug }: { initialMode?: Mode; replaySlug?: string }) {
  const [mode, setMode] = useState<Mode>(initialMode);
  return (
    <div className={styles.lab}>
      <div className={styles.head}>
        <ChipGroup
          label="Modo do laboratório"
          value={mode}
          onChange={setMode}
          items={[
            { value: 'replay', label: 'Replay guiado' },
            { value: 'live', label: 'Ao vivo' },
          ]}
        />
        <span className={styles.meta}>Simulação educacional: conta fictícia, nenhuma ordem é enviada a corretora.</span>
      </div>
      {mode === 'replay' ? <ReplayLab initialSlug={replaySlug} /> : <LiveLab />}
    </div>
  );
}

// ---------- Replay guiado ----------

function ReplayLab({ initialSlug }: { initialSlug?: string }) {
  const list = useApi<LabReplaySummary[]>('/api/lms/replays');
  const [slug, setSlug] = useState<string | null>(initialSlug ?? null);
  const current = slug ?? list.data?.[0]?.slug ?? null;
  const replay = useApi<LabReplay>(current ? `/api/lms/replays/${current}` : null);
  return (
    <>
      {list.data && list.data.length > 1 && (
        <Select label="Dia para treinar" value={current ?? ''} onChange={(e) => setSlug(e.target.value)}>
          {list.data.map((r) => (
            <option key={r.slug} value={r.slug}>
              {r.title} ({formatDay(r.date)})
            </option>
          ))}
        </Select>
      )}
      <AsyncContent state={replay} loading={<Skeleton height={320} />} empty={<EmptyState title="Nenhum replay disponível" description="Os replays aparecem aqui quando forem publicados." />}>
        {(r) => <ReplayPlayer key={r.slug} replay={r} />}
      </AsyncContent>
    </>
  );
}

const SPEEDS = { '1': 1000, '2': 500, '4': 250 } as const;

function ReplayPlayer({ replay }: { replay: LabReplay }) {
  const bars = replay.bars as LabBar[];
  // Começa no último candle do contexto: a primeira legenda (pausa de decisão) aparece antes do evento.
  const start = Math.max(0, replay.context_bars - 1);
  const [cursor, setCursor] = useState(start);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<keyof typeof SPEEDS>('1');
  const [lab, setLab] = useState<LabState>(() => initLab(START_BALANCE));
  const cursorRef = useRef(cursor);
  cursorRef.current = cursor;
  const ended = cursor >= bars.length - 1;

  function step() {
    const next = cursorRef.current + 1;
    if (next >= bars.length) {
      setPlaying(false);
      return;
    }
    cursorRef.current = next;
    setCursor(next);
    setLab((s) => onBar(s, bars[next], replay.spread));
    // Legenda que pede decisão pausa o replay, como um professor apertando pause.
    if (replay.captions.some((c) => c.at === next && /pause|onde ficaria|rompimento ou/i.test(c.text))) setPlaying(false);
  }

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(step, SPEEDS[speed]);
    return () => clearInterval(id);
  }, [playing, speed]); // eslint-disable-line react-hooks/exhaustive-deps

  const caption = [...replay.captions].reverse().find((c) => c.at <= cursor);
  const bar = bars[cursor];
  const data = useMemo(() => toChartData(bars.slice(0, cursor + 1), replay.label), [bars, cursor, replay.label]);

  function reset() {
    setPlaying(false);
    setCursor(start);
    setLab(initLab(START_BALANCE));
  }

  return (
    <div className={styles.grid}>
      <div className={styles.chartCol}>
        <div className={styles.titleRow}>
          <strong>{replay.title}</strong>
          <span className={styles.meta}>
            {replay.label}, {formatDay(replay.date)}, {replay.timezone.toLowerCase()} {timeOf(bar.t)}
          </span>
        </div>
        <p className={styles.meta}>{replay.summary}</p>
        <ChartPanel data={data} timeframe={findTimeframe('5D')} panels={[]} levels={levelsFor(lab)} height={300} label={replay.label} />
        <div className={styles.caption} aria-live="polite">
          {caption ? caption.text : 'Aperte play. O replay para sozinho quando for hora de decidir.'}
        </div>
        <div className={styles.controls}>
          <Button size="sm" variant="primary" icon={playing ? <Pause {...ICON} /> : <Play {...ICON} />} disabled={ended} onClick={() => setPlaying((p) => !p)}>
            {playing ? 'Pausar' : ended ? 'Fim do replay' : 'Play'}
          </Button>
          <Button size="sm" variant="ghost" icon={<StepForward {...ICON} />} disabled={ended || playing} onClick={step}>
            Próxima barra
          </Button>
          <ChipGroup
            label="Velocidade"
            value={speed}
            onChange={setSpeed}
            items={[
              { value: '1', label: '1x' },
              { value: '2', label: '2x' },
              { value: '4', label: '4x' },
            ]}
          />
          <Button size="sm" variant="ghost" icon={<RotateCcw {...ICON} />} onClick={reset}>
            Recomeçar
          </Button>
        </div>
        <p className={styles.meta}>Dica do professor: {replay.hint}</p>
      </div>
      <LabAccount state={lab} onChange={setLab} price={bar.c} spread={replay.spread} at={bar.t} digits={replay.digits} />
      {/* Celular: controles do replay presos no rodapé, para dar play olhando a boleta. */}
      <div className={styles.mobileBar} role="group" aria-label="Controles do replay">
        <Button size="sm" variant="primary" icon={playing ? <Pause {...ICON} /> : <Play {...ICON} />} disabled={ended} onClick={() => setPlaying((p) => !p)}>
          {playing ? 'Pausar' : 'Play'}
        </Button>
        <Button size="sm" variant="ghost" icon={<StepForward {...ICON} />} disabled={ended || playing} onClick={step} aria-label="Próxima barra" />
        <span className={styles.mobileBarInfo}>
          {timeOf(bar.t)} · {formatNumber(bar.c, replay.digits)}
          <strong className={equity(lab, bar.c, replay.spread) >= START_BALANCE ? styles.up : styles.down}>
            US$ {formatNumber(equity(lab, bar.c, replay.spread), 0)}
          </strong>
        </span>
      </div>
    </div>
  );
}

// ---------- Ao vivo ----------

const LIVE = [
  { symbol: 'QQQ', label: 'QQQ (ETF do Nasdaq 100)', spread: 0.02, digits: 2 },
  { symbol: 'NQ=F', label: 'Nasdaq 100 futuro (NQ=F)', spread: 0.5, digits: 2 },
  { symbol: 'GC=F', label: 'Ouro futuro (GC=F)', spread: 0.2, digits: 2 },
  { symbol: 'EURUSD=X', label: 'Euro/dólar (EURUSD)', spread: 0.0001, digits: 5 },
] as const;

function LiveLab() {
  const [symbol, setSymbol] = useState<string>(LIVE[0].symbol);
  const spec = LIVE.find((x) => x.symbol === symbol) ?? LIVE[0];
  return (
    <>
      <Select label="Ativo" value={symbol} onChange={(e) => setSymbol(e.target.value)}>
        {LIVE.map((x) => (
          <option key={x.symbol} value={x.symbol}>
            {x.label}
          </option>
        ))}
      </Select>
      <LiveAccount key={spec.symbol} spec={spec} />
    </>
  );
}

function LiveAccount({ spec }: { spec: (typeof LIVE)[number] }) {
  const key = `oneb.academia.lab.live.${spec.symbol}`;
  const chart = useApi<ChartData>(`/api/chart/${encodeURIComponent(spec.symbol)}?period=1d&interval=1m`, {
    pollMs: 15_000,
    isEmpty: (d) => d.close.length === 0,
  });
  const [lab, setLab] = useState<LabState>(() => readJson<LabState>(key, initLab()));
  const processed = useRef(0);
  const bars = useMemo(() => (chart.data ? chartBars(chart.data) : []), [chart.data]);

  useEffect(() => {
    writeJson(key, lab);
  }, [key, lab]);

  // Só barras já fechadas decidem stop e alvo; a última (em formação) só dá o preço.
  useEffect(() => {
    const closed = bars.slice(0, -1).filter((b) => b.t > processed.current);
    if (!closed.length) return;
    processed.current = closed[closed.length - 1].t;
    setLab((s) => closed.reduce((st, b) => onBar(st, b, spec.spread), s));
  }, [bars, spec.spread]);

  const last = bars[bars.length - 1];
  const stale = last ? Date.now() - last.t > 10 * 60_000 : true;
  return (
    <div className={styles.grid}>
      <div className={styles.chartCol}>
        <AsyncContent state={chart} loading={<Skeleton height={300} />} empty={<EmptyState title="Sem cotação agora" description="Tente outro ativo ou volte no horário de pregão." />}>
          {(data) => <ChartPanel data={data} timeframe={findTimeframe('1D')} panels={[]} levels={levelsFor(lab)} height={300} label={spec.label} />}
        </AsyncContent>
        <p className={styles.meta}>
          Cotação de 1 minuto de fonte gratuita, com atraso de até 15 min, atualizada a cada 15 s. {stale && last ? <Badge tone="warning">Mercado parado: último preço às {timeOf(last.t)}</Badge> : null}
        </p>
      </div>
      <LabAccount state={lab} onChange={setLab} price={last?.c ?? null} spread={spec.spread} at={last?.t ?? 0} digits={spec.digits} />
    </div>
  );
}

// ---------- Conta, boleta e placar ----------

function LabAccount({ state, onChange, price, spread, at, digits }: { state: LabState; onChange: (s: LabState) => void; price: number | null; spread: number; at: number; digits: number }) {
  const [riskPct, setRiskPct] = useState('1');
  const [stop, setStop] = useState('');
  const [target, setTarget] = useState('');
  const [units, setUnits] = useState('');
  const [error, setError] = useState<string | null>(null);
  const q = price === null ? null : quote(price, spread);
  const stats = labStats(state.trades);
  const num = (v: string) => (v.trim() === '' ? null : Number(v.replace(',', '.')));

  function send(side: Side) {
    if (price === null || q === null) return;
    const s = num(stop);
    const t = num(target);
    const fill = side === 'BUY' ? q.ask : q.bid;
    const manual = num(units);
    const qty = manual ?? (s !== null ? sizeByRisk(state.balance, Number(riskPct.replace(',', '.')), fill, s) : 0);
    if (!manual && s === null) {
      setError('Defina um stop (para calcular o tamanho pelo risco) ou informe a quantidade.');
      return;
    }
    const res = openPosition(state, { side, units: qty, stop: s, target: t }, price, spread, at);
    setError(res.error);
    if (!res.error) onChange(res.state);
  }

  return (
    <aside className={styles.account} aria-label="Conta simulada">
      <div className={styles.stats}>
        <Stat label="Saldo" value={`US$ ${formatNumber(state.balance, 2)}`} />
        <Stat label="Patrimônio" value={`US$ ${formatNumber(equity(state, price, spread), 2)}`} />
      </div>
      <div className={styles.quote}>
        <span>Venda (bid) {q ? formatNumber(q.bid, digits) : '—'}</span>
        <span>Compra (ask) {q ? formatNumber(q.ask, digits) : '—'}</span>
      </div>
      <div className={styles.ticket}>
        <Input label="Stop (preço)" inputMode="decimal" value={stop} onChange={(e) => setStop(e.target.value)} />
        <Input label="Alvo (preço)" inputMode="decimal" value={target} onChange={(e) => setTarget(e.target.value)} />
        <Input label="Risco por operação (%)" inputMode="decimal" value={riskPct} onChange={(e) => setRiskPct(e.target.value)} />
        <Input label="Quantidade (opcional)" inputMode="decimal" value={units} onChange={(e) => setUnits(e.target.value)} hint="Em branco: calculada pelo risco até o stop." />
      </div>
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
      <div className={styles.sides}>
        <Button variant="primary" disabled={price === null} onClick={() => send('BUY')}>
          Comprar
        </Button>
        <Button variant="secondary" disabled={price === null} onClick={() => send('SELL')}>
          Vender
        </Button>
      </div>

      {state.positions.length > 0 && (
        <section aria-label="Posições abertas">
          <h3 className={styles.subTitle}>Posições abertas</h3>
          <ul className={styles.list}>
            {state.positions.map((p) => (
              <li key={p.id}>
                <span>
                  {p.side === 'BUY' ? 'Compra' : 'Venda'} {formatNumber(p.units, 2)} a {formatNumber(p.entry, digits)}
                  {p.stop !== null ? `, stop ${formatNumber(p.stop, digits)}` : ', sem stop'}
                  {p.target !== null ? `, alvo ${formatNumber(p.target, digits)}` : ''}
                </span>
                <span className={styles.row}>
                  <strong className={price !== null && openPnl(p, price, spread) >= 0 ? styles.up : styles.down}>US$ {price !== null ? formatNumber(openPnl(p, price, spread), 2) : '—'}</strong>
                  <Button size="sm" variant="ghost" disabled={price === null} onClick={() => price !== null && onChange(closePosition(state, p.id, price, spread, at))}>
                    Fechar
                  </Button>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-label="Seu placar">
        <h3 className={styles.subTitle}>Seu placar</h3>
        <div className={styles.stats}>
          <Stat label="Operações" value={String(stats.count)} />
          <Stat label="Acerto" value={stats.winRate === null ? '—' : `${formatNumber(stats.winRate * 100, 0)}%`} />
          <Stat label="Expectativa" value={stats.expectancyR === null ? '—' : `${formatNumber(stats.expectancyR, 2)}R`} sub="média por operação" />
        </div>
        {stats.count > 0 && stats.winRate !== null && stats.expectancyR !== null && stats.winRate >= 0.5 && stats.expectancyR < 0 && (
          <p className={styles.meta}>Você acertou a maioria e mesmo assim perdeu: é a aula “Acerto não é lucro” na prática.</p>
        )}
        {state.trades.length > 0 && (
          <ul className={styles.list}>
            {state.trades
              .slice(-6)
              .reverse()
              .map((t) => (
                <li key={`${t.id}-${t.closedAt}`}>
                  <span>
                    {t.side === 'BUY' ? 'Compra' : 'Venda'} saiu no {t.reason === 'STOP' ? 'stop' : t.reason === 'TARGET' ? 'alvo' : 'manual'}
                  </span>
                  <strong className={t.pnl >= 0 ? styles.up : styles.down}>
                    {t.r !== null ? `${formatNumber(t.r, 2)}R` : `US$ ${formatNumber(t.pnl, 2)}`}
                  </strong>
                </li>
              ))}
          </ul>
        )}
        <Button size="sm" variant="ghost" onClick={() => onChange(initLab())}>
          Zerar conta
        </Button>
      </section>
    </aside>
  );
}

// ---------- utilitários ----------

function toChartData(bars: LabBar[], symbol: string): ChartData {
  const nulls = bars.map(() => null);
  return {
    symbol,
    timestamps: bars.map((b) => new Date(b.t).toISOString()),
    open: bars.map((b) => b.o),
    high: bars.map((b) => b.h),
    low: bars.map((b) => b.l),
    close: bars.map((b) => b.c),
    volume: nulls,
    rsi: nulls,
    macd: nulls,
    macd_signal: nulls,
    ema_fast: nulls,
    ema_slow: nulls,
  };
}

function chartBars(d: ChartData): LabBar[] {
  const out: LabBar[] = [];
  d.timestamps.forEach((ts, i) => {
    const o = d.open[i];
    const h = d.high[i];
    const l = d.low[i];
    const c = d.close[i];
    if (o !== null && h !== null && l !== null && c !== null) out.push({ t: new Date(ts).getTime(), o, h, l, c });
  });
  return out;
}

function levelsFor(state: LabState): PriceLevel[] {
  return state.positions.flatMap((p) => [
    { label: `Entrada ${p.id}`, value: p.entry, colorVar: '--chart-level-entry' },
    ...(p.stop !== null ? [{ label: `Stop ${p.id}`, value: p.stop, colorVar: '--chart-level-stop' }] : []),
    ...(p.target !== null ? [{ label: `Alvo ${p.id}`, value: p.target, colorVar: '--chart-level-target' }] : []),
  ]);
}

function timeOf(t: number): string {
  return new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit', timeZone: 'America/Sao_Paulo' }).format(t);
}

function formatDay(iso: string): string {
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}
