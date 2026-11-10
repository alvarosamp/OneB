import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Bell, Check, MessagesSquare, Plus } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { useQueryTab } from '../hooks/useQueryTab';
import { useToast } from '../context/ToastContext';
import { ChartPanel, type PriceLevel } from '../components/terminal/ChartPanel';
import { AnalysisPanel, type Fact } from '../components/terminal/AnalysisPanel';
import { DataAge } from '../components/terminal/DataAge';
import { AsyncContent, Button, ChangeText, EmptyState, ICON, Skeleton, SkeletonLines, Tabs } from '../components/ui';
import { buttonClass } from '../components/ui/buttonClass';
import { TICKER } from '../content/instruments';
import { chartPath, TIMEFRAMES, type Timeframe } from '../lib/timeframes';
import { readMarket, REGIME_LABEL } from '../lib/marketRead';
import { formatNumber, formatPrice, formatSigned, isNum } from '../lib/format';
import { lastValue } from '../lib/indicators';
import { ptBR } from '../lib/text';
import { addToWatchlist, analyzeHref, createAlertHref, normalizeSymbol } from '../lib/watchlist';
import type { ChartData, RegimeReport, TechnicalAnalysis, WatchlistItem } from '../types';
import styles from './AtivoDetalhe.module.css';

type TfId = Timeframe['id'];
const TF_IDS = TIMEFRAMES.map((t) => t.id);

/** Tela do ativo: gráfico protagonista + leitura lateral com justificativas. */
export function AtivoDetalhe() {
  const { symbol: raw = '' } = useParams();
  const symbol = normalizeSymbol(decodeURIComponent(raw));
  const [tfId, setTfId] = useQueryTab<TfId>(TF_IDS, '5D', 'tf');
  const tf = TIMEFRAMES.find((t) => t.id === tfId)!;

  const chart = useApi<ChartData>(chartPath(symbol, tf), { pollMs: tf.intraday ? 60_000 : 10 * 60_000, isEmpty: (d) => d.close.length === 0 });
  const techPath = `/api/technical/analysis/${encodeURIComponent(symbol)}?period=${tf.intraday ? '5d' : '6mo'}&interval=${tf.intraday ? '15m' : '1d'}`;
  const tech = useApi<TechnicalAnalysis>(techPath, { pollMs: 5 * 60_000 });
  const regime = useApi<RegimeReport>(`/api/regime/${encodeURIComponent(symbol)}`, { pollMs: 30 * 60_000 });
  const watchlist = useApi<WatchlistItem[]>('/api/watchlist');

  const inWatchlist = watchlist.data?.find((w) => w.symbol === symbol) ?? null;
  const known = TICKER.find((t) => t.spark === symbol);
  const name = inWatchlist?.label || known?.name || null;

  const last = chart.data ? lastValue(chart.data.close) : null;
  const change = tech.data?.change_pct ?? null;

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.identity}>
          <h1 className={styles.symbol}>{symbol}</h1>
          {name && <span className={styles.name}>{name}</span>}
        </div>
        <div className={styles.quote}>
          <span className={styles.price}>{isNum(last) ? formatPrice(last, symbol) : chart.status === 'loading' ? <Skeleton width={120} height={26} /> : '—'}</span>
          {isNum(last) && <ChangeText value={change} className={styles.change} />}
          {chart.data && <DataAge at={chart.data.timestamps[chart.data.timestamps.length - 1]} staleAfterMin={tf.intraday ? 30 : 60 * 24 * 3} prefix="último candle" refreshError={chart.error} />}
        </div>
        <Actions symbol={symbol} inWatchlist={!!inWatchlist} onAdded={(item) => watchlist.mutate((prev) => [...(prev ?? []), item])} />
      </header>

      <Tabs items={TIMEFRAMES.map((t) => ({ value: t.id, label: t.label }))} value={tfId} onChange={setTfId} label="Período do gráfico" variant="segmented" />

      <div className={styles.body}>
        <section className={styles.chart} aria-label={`Gráfico de ${symbol}`}>
          <AsyncContent
            state={chart}
            loading={<Skeleton height={560} />}
            empty={
              <EmptyState
                center
                title={`Sem histórico de ${symbol} neste período`}
                description={chart.error ?? 'O provedor não retornou candles. Confira o símbolo (ex.: PETR4.SA, GC=F, ^GSPC) ou tente outro período.'}
              />
            }
            errorTitle="Não foi possível carregar o gráfico"
          >
            {(data) => <ChartPanel data={data} timeframe={tf} panels={['volume', 'rsi', 'macd']} height={400} label={symbol} levels={levelsFrom(tech.data)} />}
          </AsyncContent>
        </section>
        <aside className={styles.side}>
          <AssetRead symbol={symbol} tf={tf} tech={tech} regime={regime} chart={chart.data} />
        </aside>
      </div>
    </div>
  );
}

function Actions({ symbol, inWatchlist, onAdded }: { symbol: string; inWatchlist: boolean; onAdded: (i: WatchlistItem) => void }) {
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  async function add() {
    setAdding(true);
    try {
      const item = await addToWatchlist(symbol);
      onAdded(item);
      toast(`${symbol} adicionado à watchlist`, 'success');
    } catch (err) {
      toast(err instanceof Error ? `Não foi possível adicionar: ${err.message}` : 'Não foi possível adicionar', 'error');
    } finally {
      setAdding(false);
    }
  }
  return (
    <div className={styles.actions}>
      <Link to={analyzeHref(symbol)} className={buttonClass({ size: 'sm' })}>
        <MessagesSquare {...ICON} aria-hidden="true" />
        Analisar no Assistente
      </Link>
      <Link to={createAlertHref(symbol)} className={buttonClass({ size: 'sm' })}>
        <Bell {...ICON} aria-hidden="true" />
        Criar alerta
      </Link>
      {inWatchlist ? (
        <Button size="sm" variant="ghost" icon={<Check {...ICON} />} disabled>
          Na watchlist
        </Button>
      ) : (
        <Button size="sm" variant="primary" icon={<Plus {...ICON} />} loading={adding} onClick={add}>
          Adicionar à watchlist
        </Button>
      )}
    </div>
  );
}

function levelsFrom(tech: TechnicalAnalysis | null): PriceLevel[] {
  if (!tech) return [];
  const out: PriceLevel[] = [];
  if (isNum(tech.support)) out.push({ label: 'Suporte', value: tech.support, colorVar: '--chart-level-support' });
  if (isNum(tech.resistance)) out.push({ label: 'Resistência', value: tech.resistance, colorVar: '--chart-level-resistance' });
  return out;
}

interface AssetReadProps {
  symbol: string;
  tf: Timeframe;
  tech: ReturnType<typeof useApi<TechnicalAnalysis>>;
  regime: ReturnType<typeof useApi<RegimeReport>>;
  chart: ChartData | null;
}

function AssetRead({ symbol, tf, tech, regime, chart }: AssetReadProps) {
  const read = useMemo(() => readMarket(regime.data, tech.data, tf.intraday ? 'intradiário' : 'gráfico diário'), [regime.data, tech.data, tf.intraday]);
  const t = tech.data;

  if (tech.status === 'loading' && regime.status === 'loading') {
    return (
      <div className={styles.readLoading}>
        <Skeleton width={160} height={22} />
        <SkeletonLines lines={8} />
      </div>
    );
  }
  if (!read || !t) {
    return (
      <EmptyState
        title="Sem leitura para este ativo"
        description={tech.error ?? regime.error ?? 'A análise técnica precisa de candles recentes. Tente outro período ou confirme o símbolo.'}
        action={
          <Button size="sm" onClick={() => (tech.retry(), regime.retry())}>
            Tentar de novo
          </Button>
        }
      />
    );
  }

  const local = regime.data?.local_regime ?? null;
  const macd = t.signals.find((s) => s.name === 'macd');
  const volumeSignal = t.signals.find((s) => s.name === 'volume');
  const rsiVal = (chart ? lastValue(chart.rsi) : null) ?? t.rsi;
  const setups = t.setups.filter((s) => s.status !== 'ARCHIVED');

  const facts: Fact[] = [
    {
      label: 'Regime',
      value: local ? REGIME_LABEL[local.label] ?? local.label : 'sem histórico',
      note: local ? `diário, score ${formatSigned(local.score, 0)}` : ptBR(regime.error ?? 'precisa de 55 candles diários'),
      concept: 'regime',
    },
    { label: 'Tendência', value: ptBR(t.trend), note: `${tf.intraday ? '15 min' : 'diário'}, preço vs EMA 9 e 21`, concept: 'ema' },
    {
      label: 'Momentum',
      value: isNum(rsiVal) ? `RSI ${formatNumber(rsiVal, 1)}` : '—',
      note: [isNum(rsiVal) ? (rsiVal >= 70 ? 'esticado' : rsiVal <= 30 ? 'sobrevendido' : 'zona neutra') : null, macd ? (macd.state === 'good' ? 'MACD acima do sinal' : 'MACD abaixo do sinal') : null]
        .filter(Boolean)
        .join(', '),
      concept: 'rsi',
    },
    {
      label: 'Volatilidade',
      value: ptBR(t.volatility_label),
      note: isNum(t.annualized_volatility_20) ? `anualizada 20 períodos ${formatNumber(t.annualized_volatility_20, 1)}%` : undefined,
      concept: 'atr',
    },
    {
      label: 'Risco em ATR',
      value: isNum(t.atr_14) ? formatPrice(t.atr_14, symbol) : '—',
      note: isNum(t.atr_pct) ? `1 ATR = ${formatNumber(t.atr_pct, 2)}% do preço; stop de 1 ATR` : undefined,
      concept: 'risco',
    },
    {
      label: 'Suporte e resistência',
      value: isNum(t.support) && isNum(t.resistance) ? `${formatPrice(t.support, symbol)} / ${formatPrice(t.resistance, symbol)}` : '—',
      note: isNum(t.distance_to_support_pct) && isNum(t.distance_to_resistance_pct) ? `a ${formatNumber(Math.abs(t.distance_to_support_pct), 2)}% e ${formatNumber(Math.abs(t.distance_to_resistance_pct), 2)}%` : undefined,
      concept: 'suporte',
    },
  ];
  if (volumeSignal) facts.push({ label: 'Volume', value: ptBR(volumeSignal.label), note: ptBR(volumeSignal.evidence), concept: 'volume' });
  facts.push({
    label: 'Setup registrado',
    value: setups.length ? `${setups.length} ativo(s)` : 'nenhum',
    note: setups[0] ? `${setups[0].direction === 'LONG' ? 'viés de alta' : 'viés de baixa'}, entrada ${formatPrice(setups[0].entry_price, symbol)}, stop ${formatPrice(setups[0].stop_price, symbol)}` : 'registre na Análise › Técnica',
  });

  return (
    <AnalysisPanel
      title="Leitura do ativo"
      meta={<DataAge at={tech.lastUpdated} />}
      state={read.state}
      bias={read.bias}
      evidences={read.evidences}
      facts={facts}
      footer={
        <span className={styles.readNote}>
          Leitura dos dados coletados, não recomendação. <Link to={`/analise?tab=tecnica&symbol=${encodeURIComponent(symbol)}`}>Abrir na Análise técnica</Link>
        </span>
      }
    />
  );
}
