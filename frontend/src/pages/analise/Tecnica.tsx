import { useMemo, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Trash2 } from 'lucide-react';
import { api } from '../../api/client';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../context/ToastContext';
import { ChartPanel, type PriceLevel } from '../../components/terminal/ChartPanel';
import { DataAge } from '../../components/terminal/DataAge';
import { ConceptLink } from '../../components/terminal/ConceptLink';
import { AsyncContent, Badge, Button, EmptyState, ICON, Input, Section, Select, Skeleton, SkeletonLines, Table, Tabs, Textarea, type Column } from '../../components/ui';
import { chartPath, TIMEFRAMES, type Timeframe } from '../../lib/timeframes';
import { formatCurrency, formatNumber, formatPrice, formatSignedPct, isNum } from '../../lib/format';
import { ptBR } from '../../lib/text';
import { normalizeSymbol, SYMBOL_RE } from '../../lib/watchlist';
import type { ChartData, TechnicalAnalysis, TechnicalEdgeRanking, TechnicalLevel, TradeSetup, WatchlistItem } from '../../types';
import styles from './Analise.module.css';

const KIND_LABEL: Record<string, string> = {
  ZONE: 'Zona',
  SUPPORT: 'Suporte',
  RESISTANCE: 'Resistência',
  ENTRY: 'Entrada',
  TARGET: 'Alvo',
  STOP: 'Stop',
};

const KIND_TOKEN: Record<string, string> = {
  ZONE: '--chart-level-zone',
  SUPPORT: '--chart-level-support',
  RESISTANCE: '--chart-level-resistance',
  ENTRY: '--chart-level-entry',
  TARGET: '--chart-level-target',
  STOP: '--chart-level-stop',
};

const SIGNAL_TONE: Record<string, 'info' | 'warning' | 'neutral'> = { good: 'info', warn: 'warning', danger: 'warning', neutral: 'neutral' };

type TfId = Timeframe['id'];

/** Análise › Técnica (antiga Mesa técnica): gráfico, leitura, níveis, setups e pesquisa de edge. */
export function Tecnica() {
  const [params, setParams] = useSearchParams();
  const watchlist = useApi<WatchlistItem[]>('/api/watchlist');
  const symbol = normalizeSymbol(params.get('symbol') ?? watchlist.data?.[0]?.symbol ?? 'QQQ');
  const tfId = (TIMEFRAMES.some((t) => t.id === params.get('tf')) ? params.get('tf') : '5D') as TfId;
  const tf = TIMEFRAMES.find((t) => t.id === tfId)!;
  const [input, setInput] = useState('');

  const chart = useApi<ChartData>(chartPath(symbol, tf), { pollMs: 60_000, isEmpty: (d) => d.close.length === 0 });
  const analysis = useApi<TechnicalAnalysis>(`/api/technical/analysis/${encodeURIComponent(symbol)}?period=${tf.intraday ? '5d' : '6mo'}&interval=${tf.intraday ? '15m' : '1d'}`, { pollMs: 60_000 });

  function set(key: string, value: string) {
    const p = new URLSearchParams(params);
    p.set(key, value);
    setParams(p, { replace: true });
  }

  function goSymbol(e: FormEvent) {
    e.preventDefault();
    const s = normalizeSymbol(input);
    if (SYMBOL_RE.test(s)) {
      set('symbol', s);
      setInput('');
    }
  }

  const a = analysis.data;
  const levels = useMemo<PriceLevel[]>(() => {
    if (!a) return [];
    const out: PriceLevel[] = [];
    if (isNum(a.support)) out.push({ label: 'Suporte (80 candles)', value: a.support, colorVar: '--chart-level-auto' });
    if (isNum(a.resistance)) out.push({ label: 'Resistência (80 candles)', value: a.resistance, colorVar: '--chart-level-auto' });
    for (const l of a.levels) out.push({ label: l.label || KIND_LABEL[l.kind] || l.kind, value: l.price, colorVar: KIND_TOKEN[l.kind] ?? '--chart-level-zone' });
    for (const s of a.setups) {
      out.push({ label: `Entrada #${s.id}`, value: s.entry_price, colorVar: '--chart-level-entry' });
      out.push({ label: `Stop #${s.id}`, value: s.stop_price, colorVar: '--chart-level-stop' });
      out.push({ label: `Alvo #${s.id}`, value: s.target_price, colorVar: '--chart-level-target' });
    }
    return out;
  }, [a]);

  return (
    <div className={styles.stack}>
      <div className={styles.toolbar}>
        <Select label="Ativo da watchlist" value={watchlist.data?.some((w) => w.symbol === symbol) ? symbol : ''} onChange={(e) => e.target.value && set('symbol', e.target.value)} className={styles.w220}>
          <option value="">{watchlist.data?.some((w) => w.symbol === symbol) ? '' : `${symbol} (fora da watchlist)`}</option>
          {(watchlist.data ?? []).map((w) => (
            <option key={w.id} value={w.symbol}>
              {w.symbol}
              {w.label ? `, ${w.label}` : ''}
            </option>
          ))}
        </Select>
        <form onSubmit={goSymbol} className={styles.inline}>
          <Input label="Outro símbolo" value={input} onChange={(e) => setInput(e.target.value.toUpperCase())} placeholder="PETR4.SA" className={styles.w140} />
          <Button type="submit">Abrir</Button>
        </form>
        <Tabs items={TIMEFRAMES.map((t) => ({ value: t.id, label: t.label }))} value={tfId} onChange={(v) => set('tf', v)} label="Período" variant="segmented" />
      </div>

      <div className={styles.workbench}>
        <section aria-label={`Gráfico de ${symbol}`} className={styles.chart}>
          <div className={styles.chartHead}>
            <h2 className={styles.h2}>{symbol}</h2>
            {a && (
              <>
                <span className={styles.bigNum}>{formatPrice(a.price, symbol)}</span>
                <span className={isNum(a.change_pct) && a.change_pct < 0 ? 'down num' : 'up num'}>{formatSignedPct(a.change_pct)}</span>
              </>
            )}
            {chart.lastUpdated && <DataAge at={chart.data?.timestamps.at(-1)} staleAfterMin={tf.intraday ? 30 : 60 * 24 * 3} prefix="último candle" />}
          </div>
          <AsyncContent state={chart} loading={<Skeleton height={480} />} empty={<EmptyState center title={`Sem candles de ${symbol}`} description={chart.error ?? 'Confira o símbolo ou tente outro período.'} />} errorTitle="Gráfico indisponível">
            {(d) => <ChartPanel data={d} timeframe={tf} panels={['volume', 'rsi']} height={380} levels={levels} label={symbol} />}
          </AsyncContent>
        </section>

        <aside className={styles.side} aria-label="Estudo">
          <AsyncContent state={analysis} loading={<SkeletonLines lines={10} />} empty={<EmptyState title="Sem leitura técnica" description={analysis.error ?? undefined} />} errorTitle="Leitura indisponível">
            {(t) => <Study symbol={symbol} a={t} onChange={analysis.retry} />}
          </AsyncContent>
        </aside>
      </div>

      <EdgeResearch watchlist={watchlist.data ?? []} onPick={(s) => set('symbol', s)} />
    </div>
  );
}

function Study({ symbol, a, onChange }: { symbol: string; a: TechnicalAnalysis; onChange: () => void }) {
  const toast = useToast();
  const [level, setLevel] = useState({ label: '', kind: 'ZONE', price: '', notes: '' });
  const [setup, setSetup] = useState({ direction: 'LONG', entry_price: '', stop_price: '', target_price: '', thesis: '', invalidation: '' });

  async function addLevel(e: FormEvent) {
    e.preventDefault();
    const price = Number(level.price);
    if (!(price > 0)) return toast('Informe um preço válido para o nível', 'error');
    try {
      await api.post<TechnicalLevel>('/api/technical/levels', { symbol, label: level.label || KIND_LABEL[level.kind], kind: level.kind, price, color: `level-${level.kind.toLowerCase()}`, notes: level.notes });
      setLevel({ label: '', kind: 'ZONE', price: '', notes: '' });
      onChange();
      toast('Nível salvo', 'success');
    } catch (err) {
      toast(err instanceof Error ? `Não foi possível salvar o nível: ${err.message}` : 'Não foi possível salvar o nível', 'error');
    }
  }

  async function removeLevel(l: TechnicalLevel) {
    try {
      await api.delete(`/api/technical/levels/${l.id}`);
      onChange();
      toast('Nível removido', 'success');
    } catch {
      toast('Não foi possível remover o nível', 'error');
    }
  }

  async function addSetup(e: FormEvent) {
    e.preventDefault();
    const payload = { symbol, direction: setup.direction, entry_price: Number(setup.entry_price), stop_price: Number(setup.stop_price), target_price: Number(setup.target_price), thesis: setup.thesis, invalidation: setup.invalidation };
    if (!(payload.entry_price > 0 && payload.stop_price > 0 && payload.target_price > 0)) return toast('Informe entrada, stop e alvo', 'error');
    try {
      await api.post<TradeSetup>('/api/technical/setups', payload);
      setSetup({ direction: 'LONG', entry_price: '', stop_price: '', target_price: '', thesis: '', invalidation: '' });
      onChange();
      toast('Setup registrado', 'success');
    } catch (err) {
      toast(err instanceof Error ? `Não foi possível registrar o setup: ${err.message}` : 'Não foi possível registrar o setup', 'error');
    }
  }

  async function removeSetup(s: TradeSetup) {
    try {
      await api.delete(`/api/technical/setups/${s.id}`);
      onChange();
      toast('Setup arquivado', 'success');
    } catch {
      toast('Não foi possível arquivar o setup', 'error');
    }
  }

  const rr = (s: TradeSetup) => {
    const risk = Math.abs(s.entry_price - s.stop_price);
    return risk ? Math.abs(s.target_price - s.entry_price) / risk : null;
  };

  return (
    <div className={styles.study}>
      <div>
        <h3 className={styles.h3}>
          Leitura <span className="muted">{ptBR(a.trend)}</span>
        </h3>
        <ul className={styles.signals}>
          {a.signals.map((s) => (
            <li key={s.name}>
              <Badge tone={SIGNAL_TONE[s.state] ?? 'neutral'}>{ptBR(s.label)}</Badge>
              <span className="muted">{ptBR(s.evidence)}</span>
            </li>
          ))}
        </ul>
      </div>

      <dl className={styles.numbers}>
        <dt>
          ATR 14 <ConceptLink concept="atr" />
        </dt>
        <dd className="num">
          {formatPrice(a.atr_14, symbol)} ({formatNumber(a.atr_pct, 2)}%)
        </dd>
        <dt>Volatilidade anualizada</dt>
        <dd className="num">{isNum(a.annualized_volatility_20) ? `${formatNumber(a.annualized_volatility_20, 1)}%` : '—'}</dd>
        <dt>Amplitude média</dt>
        <dd className="num">{isNum(a.avg_range_pct_20) ? `${formatNumber(a.avg_range_pct_20, 2)}%` : '—'}</dd>
        <dt>
          Até suporte / resistência <ConceptLink concept="suporte" />
        </dt>
        <dd className="num">
          {formatSignedPct(a.distance_to_support_pct)} / {formatSignedPct(a.distance_to_resistance_pct)}
        </dd>
        <dt>
          Lote de US$ 200 <ConceptLink concept="risco" />
        </dt>
        <dd className="num">
          {a.suggested_shares_200_usd} unid., risco de 1 ATR {formatCurrency(a.suggested_risk_usd_200)}
        </dd>
      </dl>

      <div>
        <h3 className={styles.h3}>Níveis do estudo</h3>
        {a.levels.length ? (
          <ul className={styles.itemList}>
            {a.levels.map((l) => (
              <li key={l.id}>
                <span>
                  <strong>{l.label}</strong> <span className="muted">{KIND_LABEL[l.kind] ?? l.kind}</span>
                </span>
                <span className="num">{formatPrice(l.price, symbol)}</span>
                <Button size="sm" variant="ghost" iconOnly icon={<Trash2 {...ICON} />} aria-label={`Remover nível ${l.label}`} onClick={() => removeLevel(l)} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Nenhum nível salvo para {symbol}.</p>
        )}
        <form className={styles.miniForm} onSubmit={addLevel}>
          <Select label="Tipo" value={level.kind} onChange={(e) => setLevel((f) => ({ ...f, kind: e.target.value }))}>
            {Object.entries(KIND_LABEL).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </Select>
          <Input label="Preço" type="number" step="0.01" value={level.price} onChange={(e) => setLevel((f) => ({ ...f, price: e.target.value }))} />
          <Input label="Rótulo" value={level.label} onChange={(e) => setLevel((f) => ({ ...f, label: e.target.value }))} placeholder="Opcional" />
          <div className={styles.quick}>
            {isNum(a.support) && (
              <Button size="sm" variant="ghost" onClick={() => setLevel((f) => ({ ...f, kind: 'SUPPORT', price: String(a.support) }))}>
                Usar suporte
              </Button>
            )}
            {isNum(a.resistance) && (
              <Button size="sm" variant="ghost" onClick={() => setLevel((f) => ({ ...f, kind: 'RESISTANCE', price: String(a.resistance) }))}>
                Usar resistência
              </Button>
            )}
            <Button size="sm" type="submit">
              Salvar nível
            </Button>
          </div>
        </form>
      </div>

      <div>
        <h3 className={styles.h3}>Setups registrados</h3>
        {a.setups.length ? (
          <ul className={styles.itemList}>
            {a.setups.map((s) => (
              <li key={s.id}>
                <span>
                  <strong>#{s.id}</strong> <span className="muted">{s.direction === 'LONG' ? 'viés de alta' : 'viés de baixa'}</span>
                  <span className={styles.itemNote}>{s.thesis}</span>
                </span>
                <span className="num">
                  {formatPrice(s.entry_price, symbol)} / {formatPrice(s.stop_price, symbol)} / {formatPrice(s.target_price, symbol)}
                  <span className={styles.itemNote}>{isNum(rr(s)) ? `${formatNumber(rr(s), 2)}R` : ''}</span>
                </span>
                <Button size="sm" variant="ghost" iconOnly icon={<Trash2 {...ICON} />} aria-label={`Arquivar setup ${s.id}`} onClick={() => removeSetup(s)} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Nenhum setup registrado para {symbol}.</p>
        )}
        <form className={styles.miniForm} onSubmit={addSetup}>
          <Select label="Viés" value={setup.direction} onChange={(e) => setSetup((f) => ({ ...f, direction: e.target.value }))}>
            <option value="LONG">Alta (long)</option>
            <option value="SHORT">Baixa (short)</option>
          </Select>
          <Input label="Entrada" type="number" step="0.01" value={setup.entry_price} onChange={(e) => setSetup((f) => ({ ...f, entry_price: e.target.value }))} />
          <Input label="Stop" type="number" step="0.01" value={setup.stop_price} onChange={(e) => setSetup((f) => ({ ...f, stop_price: e.target.value }))} />
          <Input label="Alvo" type="number" step="0.01" value={setup.target_price} onChange={(e) => setSetup((f) => ({ ...f, target_price: e.target.value }))} />
          <Textarea label="Tese" rows={2} value={setup.thesis} onChange={(e) => setSetup((f) => ({ ...f, thesis: e.target.value }))} className={styles.full} />
          <Input label="Invalidação" value={setup.invalidation} onChange={(e) => setSetup((f) => ({ ...f, invalidation: e.target.value }))} className={styles.full} />
          <div className={styles.quick}>
            <Button size="sm" type="submit" variant="primary">
              Registrar setup
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function EdgeResearch({ watchlist, onPick }: { watchlist: WatchlistItem[]; onPick: (s: string) => void }) {
  const universe = Array.from(new Set([...watchlist.map((w) => w.symbol), 'AAPL', 'MSFT', 'NVDA'])).slice(0, 50);
  const edge = useApi<TechnicalEdgeRanking>(watchlist.length ? `/api/technical/edge?symbols=${encodeURIComponent(universe.join(','))}` : null, { isEmpty: (d) => d.rows.length === 0 });
  const LABEL: Record<string, string> = { OBSERVAR: 'Observar', NEUTRO: 'Neutro', FRACO: 'Fraco' };
  const columns: Column<TechnicalEdgeRanking['rows'][number]>[] = [
    { key: 'rank', header: '#', align: 'right', sortValue: (r) => r.rank ?? 999, render: (r) => <span className="num">{r.rank ?? '—'}</span> },
    { key: 'ativo', header: 'Ativo', render: (r) => <strong>{r.symbol}</strong> },
    { key: 'score', header: 'Score de edge', align: 'right', sortValue: (r) => r.edge_score ?? null, render: (r) => <span className="num">{isNum(r.edge_score) ? formatNumber(r.edge_score, 1) : '—'}</span> },
    { key: 'leitura', header: 'Leitura', render: (r) => (r.status === 'OK' ? (LABEL[r.label ?? ''] ?? r.label) : <span className="muted">sem leitura</span>) },
  ];
  return (
    <Section title="Pesquisa: força relativa" divided meta={edge.data ? `horizonte de ${edge.data.horizon_days} dias contra ${edge.data.benchmark}` : undefined}>
      <AsyncContent state={edge} loading={<SkeletonLines lines={4} />} empty={<p className="muted">Adicione ativos à watchlist para comparar a força relativa.</p>} errorTitle="Pesquisa indisponível">
        {(d) => (
          <>
            <Table caption="Força relativa" columns={columns} rows={d.rows} rowKey={(r) => r.symbol} onRowClick={(r) => onPick(r.symbol)} rowLabel={(r) => `Abrir ${r.symbol} no estudo`} initialSort={{ key: 'rank', dir: 'asc' }} dense />
            <p className={styles.note}>{ptBR(d.research_note)}</p>
          </>
        )}
      </AsyncContent>
    </Section>
  );
}
