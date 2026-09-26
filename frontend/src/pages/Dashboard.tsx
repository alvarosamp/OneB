import { useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { useRadar } from '../hooks/useRadar';
import { useQueryTab } from '../hooks/useQueryTab';
import { MarketTicker } from '../components/terminal/MarketTicker';
import { ChartPanel } from '../components/terminal/ChartPanel';
import { AnalysisPanel } from '../components/terminal/AnalysisPanel';
import { AttentionLevel } from '../components/terminal/AttentionLevel';
import { DataAge } from '../components/terminal/DataAge';
import {
  AsyncContent,
  Badge,
  ChangeText,
  EmptyState,
  ErrorState,
  ICON_SM,
  Section,
  Skeleton,
  SkeletonLines,
  Table,
  Tabs,
  type Column,
} from '../components/ui';
import { buttonClass } from '../components/ui/buttonClass';
import { readMarket } from '../lib/marketRead';
import { chartPath, TIMEFRAMES, type Timeframe } from '../lib/timeframes';
import { formatDateTime, formatLongDate, formatNumber, formatPrice, formatSigned, formatTime, isNum } from '../lib/format';
import { ptBR } from '../lib/text';
import type { RadarRow } from '../hooks/useRadar';
import type {
  ChartData,
  DailyMarketSummary,
  DashboardSummary,
  EarningsEvent,
  EconomicEvent,
  GlobalNewsItem,
  RegimeReport,
  TechnicalAnalysis,
} from '../types';
import styles from './Dashboard.module.css';

const HERO_SYMBOL = 'NQ=F';
const HERO_TFS = TIMEFRAMES.filter((t) => ['1D', '5D', '1M'].includes(t.id));
type HeroTf = '1D' | '5D' | '1M';

/** Hoje: "o que está acontecendo e onde devo olhar primeiro?" */
export function Dashboard() {
  const today = formatLongDate(new Date());
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>Hoje</h1>
        <span className={styles.date}>{today}</span>
      </header>
      <MarketTicker />
      <div className={styles.hero}>
        <HeroChart />
        <DailyRead />
      </div>
      <RadarBlock />
      <div className={styles.feeds}>
        <NewsBlock />
        <CalendarBlock />
        <AlertsBlock />
      </div>
    </div>
  );
}

function HeroChart() {
  const [tfId, setTfId] = useQueryTab<HeroTf>(['1D', '5D', '1M'], '5D', 'tf');
  const tf = HERO_TFS.find((t) => t.id === tfId) as Timeframe;
  const chart = useApi<ChartData>(chartPath(HERO_SYMBOL, tf), { pollMs: 60_000, isEmpty: (d) => d.close.length === 0 });
  const last = chart.data ? lastClose(chart.data) : null;
  const dayChange = chart.data ? sessionChange(chart.data) : null;

  return (
    <section className={styles.chartArea} aria-label="Gráfico da Nasdaq">
      <div className={styles.chartHeader}>
        <div className={styles.quote}>
          <Link to={`/ativo/${encodeURIComponent(HERO_SYMBOL)}`} className={styles.symbol}>
            Nasdaq-100 futuro <span>NQ=F</span>
          </Link>
          <span className={styles.bigPrice}>{isNum(last) ? formatNumber(last) : chart.status === 'loading' ? <Skeleton width={120} height={24} /> : '—'}</span>
          {isNum(last) && <ChangeText value={dayChange} className={styles.bigChange} />}
          {chart.lastUpdated && <DataAge at={lastTimestamp(chart.data)} staleAfterMin={30} refreshError={chart.data ? chart.error : null} prefix="último candle" />}
        </div>
        <Tabs items={HERO_TFS.map((t) => ({ value: t.id as HeroTf, label: t.label }))} value={tfId} onChange={setTfId} label="Período do gráfico" variant="segmented" />
      </div>
      <AsyncContent
        state={chart}
        loading={<Skeleton height={380} />}
        empty={<EmptyState center title="Sem candles para a Nasdaq neste período" description={chart.error ?? 'O provedor de dados não retornou histórico. Tente outro período.'} />}
        errorTitle="Não foi possível carregar o gráfico"
      >
        {(data) => <ChartPanel data={data} timeframe={tf} panels={['volume']} height={340} label="Nasdaq-100 futuro" />}
      </AsyncContent>
    </section>
  );
}

function DailyRead() {
  const regime = useApi<RegimeReport>('/api/regime/NASDAQ', { pollMs: 10 * 60_000 });
  const tech = useApi<TechnicalAnalysis>(`/api/technical/analysis/${encodeURIComponent(HERO_SYMBOL)}?period=5d&interval=15m`, { pollMs: 5 * 60_000 });
  const summary = useApi<DailyMarketSummary>('/api/reports/daily-summary', { pollMs: 15 * 60_000 });

  const read = useMemo(() => readMarket(regime.data, tech.data), [regime.data, tech.data]);
  const loading = regime.status === 'loading' || tech.status === 'loading';

  if (loading && !read) {
    return (
      <aside className={styles.read} aria-busy="true">
        <h2 className={styles.readTitle}>Leitura do dia</h2>
        <Skeleton width={180} height={24} />
        <SkeletonLines lines={5} />
      </aside>
    );
  }

  if (!read) {
    const bothFailed = regime.status === 'error' && tech.status === 'error';
    return (
      <aside className={styles.read}>
        <h2 className={styles.readTitle}>Leitura do dia</h2>
        {bothFailed ? (
          <ErrorState error={regime.error ?? tech.error} onRetry={() => (regime.retry(), tech.retry())} />
        ) : (
          <EmptyState title="Sem histórico suficiente para a leitura" description="O regime precisa de pelo menos 55 candles diários da Nasdaq. Assim que o coletor tiver dados, a leitura aparece aqui." />
        )}
      </aside>
    );
  }

  const facts = [
    { label: 'Regime diário', value: read.regimeLabel ?? '—', note: isNum(read.regimeScore) ? `score ${formatSigned(read.regimeScore, 0)} de −100 a 100` : undefined, concept: 'regime' },
    { label: 'Contexto macro', value: read.macroContext ?? '—', note: 'dólar, juros, ouro e S&P 500' },
    {
      label: 'Volatilidade',
      value: read.volatility ? ptBR(read.volatility) : '—',
      note: isNum(read.atrPct) ? `ATR ${formatNumber(read.atrPct, 2)}% do preço (15 min)` : undefined,
      concept: 'atr',
    },
  ];
  if (summary.data?.market_tone) facts.push({ label: 'Tom do dia', value: ptBR(summary.data.market_tone), note: 'resumo diário da watchlist', concept: '' });

  return (
    <aside className={styles.read}>
      <AnalysisPanel
        title="Leitura do dia"
        meta={<DataAge at={tech.lastUpdated ?? regime.lastUpdated} staleAfterMin={20} />}
        state={read.state}
        bias={read.bias}
        evidences={read.evidences}
        facts={facts}
        summary={summary.data?.headline ? ptBR(summary.data.headline) : undefined}
        footer={
          <>
            <Link to="/analise" className={buttonClass({ size: 'sm' })}>
              Ver análise completa
            </Link>
            <span className={styles.readNote}>Leitura dos dados coletados, não recomendação.</span>
          </>
        }
      />
      {(regime.status === 'error' || tech.status === 'error') && (
        <p className={styles.partial}>Parte dos dados não carregou: {regime.error ?? tech.error}</p>
      )}
    </aside>
  );
}

function RadarBlock() {
  const { summary, rows, partialError } = useRadar();
  const navigate = useNavigate();
  const columns: Column<RadarRow>[] = [
    {
      key: 'ativo',
      header: 'Ativo',
      render: (r) => (
        <span className={styles.asset}>
          <strong>{r.symbol}</strong>
          {r.label && r.label !== r.symbol && <span>{r.label}</span>}
        </span>
      ),
    },
    { key: 'preco', header: 'Preço', align: 'right', render: (r) => <span className="num">{formatPrice(r.price, r.symbol)}</span> },
    { key: 'dia', header: 'Dia', align: 'right', render: (r) => (r.price === null ? <span className="muted">—</span> : <ChangeText value={r.change_pct} />) },
    { key: 'atencao', header: 'Atenção', render: (r) => <AttentionLevel score={r.attention} /> },
    { key: 'dados', header: 'Dados', align: 'right', render: (r) => <DataAge at={r.taken_at} staleAfterMin={30} prefix="" /> },
  ];
  return (
    <Section
      title="Radar de ativos"
      meta={summary.lastUpdated ? <DataAge at={summary.lastUpdated} refreshError={summary.data ? summary.error : null} refreshing={summary.refreshing} /> : null}
      actions={
        <Link to="/radar" className={styles.more}>
          Ver radar completo
        </Link>
      }
    >
      {partialError && <p className={styles.partial}>{partialError}</p>}
      <AsyncContent
        state={summary}
        loading={<SkeletonLines lines={6} height={18} />}
        empty={
          <EmptyState
            title="Nenhum ativo monitorado"
            description="Adicione um ativo à watchlist para ver o radar."
            action={
              <Link to="/watchlist" className={buttonClass({ variant: 'primary', size: 'sm' })}>
                Adicionar à watchlist
              </Link>
            }
          />
        }
        errorTitle="Não foi possível carregar o radar"
      >
        {() => (
          <Table
            caption="Ativos da watchlist ordenados por atenção"
            columns={columns}
            rows={rows.slice(0, 8)}
            rowKey={(r) => r.id}
            onRowClick={(r) => navigate(`/ativo/${encodeURIComponent(r.symbol)}`)}
            rowLabel={(r) => `Abrir ${r.symbol}`}
            dense
            stickyFirstColumn
          />
        )}
      </AsyncContent>
    </Section>
  );
}

function NewsBlock() {
  const news = useApi<GlobalNewsItem[]>('/api/global-news?limit=8', { pollMs: 10 * 60_000 });
  return (
    <Section
      title="Notícias"
      headingLevel={2}
      meta={news.lastUpdated ? <DataAge at={news.lastUpdated} /> : null}
      actions={
        <Link to="/mercado" className={styles.more}>
          Ver todas
        </Link>
      }
    >
      <AsyncContent state={news} empty={<EmptyState title="Sem notícias de impacto agora" description="O coletor busca notícias a cada 30 minutos." />} errorTitle="Notícias indisponíveis">
        {(items) => (
          <ul className={styles.feed}>
            {items.slice(0, 6).map((n) => (
              <li key={n.url}>
                <a href={n.url} target="_blank" rel="noreferrer" className={styles.feedLink}>
                  {n.headline}
                  <ArrowUpRight {...ICON_SM} aria-hidden="true" />
                  <span className="sr-only">(abre em nova aba)</span>
                </a>
                <span className={styles.feedMeta}>
                  <span>{n.source}</span>
                  <time dateTime={n.published_at}>{formatTime(n.published_at)}</time>
                  {n.impact_score >= 40 && <Badge tone="warning">impacto alto</Badge>}
                </span>
              </li>
            ))}
          </ul>
        )}
      </AsyncContent>
    </Section>
  );
}

const IMPACT: Record<string, { label: string; tone: 'warning' | 'neutral' }> = {
  high: { label: 'alto', tone: 'warning' },
  medium: { label: 'médio', tone: 'neutral' },
  low: { label: 'baixo', tone: 'neutral' },
};

function CalendarBlock() {
  const econ = useApi<EconomicEvent[]>('/api/economic-events?days_ahead=7&limit=20', { pollMs: 30 * 60_000 });
  const earnings = useApi<EarningsEvent[]>('/api/earnings-events?days_ahead=7&limit=50', { pollMs: 30 * 60_000 });
  const watch = useApi<DashboardSummary>('/api/dashboard-summary');
  const watchSymbols = new Set((watch.data?.rows ?? []).map((r) => r.symbol));

  type Item = { key: string; date: string; title: string; detail?: string; impact?: string; kind: 'macro' | 'earnings' };
  const items: Item[] = [
    ...(econ.data ?? []).map((e) => ({
      key: `e-${e.event_name}-${e.event_date}`,
      date: e.event_date,
      title: e.event_name,
      detail: [e.country, e.forecast && `proj. ${e.forecast}`, e.previous && `ant. ${e.previous}`].filter(Boolean).join(', '),
      impact: e.impact,
      kind: 'macro' as const,
    })),
    ...(earnings.data ?? [])
      .filter((e) => watchSymbols.size === 0 || watchSymbols.has(e.symbol))
      .map((e) => ({
        key: `r-${e.symbol}-${e.event_date}`,
        date: e.event_date,
        title: `Resultado de ${e.symbol}`,
        detail: isNum(e.eps_estimate) ? `LPA estimado US$ ${formatNumber(e.eps_estimate)}` : undefined,
        kind: 'earnings' as const,
      })),
  ].sort((a, b) => a.date.localeCompare(b.date));

  const state = {
    data: items,
    status: econ.status === 'loading' && earnings.status === 'loading' ? ('loading' as const) : econ.status === 'error' && earnings.status === 'error' ? ('error' as const) : items.length === 0 ? ('empty' as const) : ('ready' as const),
    error: econ.error ?? earnings.error,
    retry: () => (econ.retry(), earnings.retry()),
  };

  return (
    <Section
      title="Calendário"
      meta="próximos 7 dias"
      actions={
        <Link to="/mercado?tab=calendario" className={styles.more}>
          Ver calendário
        </Link>
      }
    >
      <AsyncContent state={state} empty={<EmptyState title="Nenhum evento nos próximos 7 dias" description="Eventos macro e resultados da sua watchlist aparecem aqui." />} errorTitle="Calendário indisponível">
        {(list) => (
          <ul className={styles.feed}>
            {list.slice(0, 7).map((i) => (
              <li key={i.key} className={styles.eventRow}>
                <time dateTime={i.date} className={styles.eventDate}>
                  {formatDateTime(i.date)}
                </time>
                <span className={styles.eventBody}>
                  <span className={styles.eventTitle}>{i.title}</span>
                  {i.detail && <span className={styles.feedMeta}>{i.detail}</span>}
                </span>
                {i.kind === 'macro' && i.impact && IMPACT[i.impact] ? (
                  <Badge tone={IMPACT[i.impact].tone}>{IMPACT[i.impact].label}</Badge>
                ) : (
                  <Badge tone="info">resultado</Badge>
                )}
              </li>
            ))}
          </ul>
        )}
      </AsyncContent>
    </Section>
  );
}

function AlertsBlock() {
  const summary = useApi<DashboardSummary>('/api/dashboard-summary', { pollMs: 20_000, isEmpty: (d) => d.alerts.length === 0 });
  return (
    <Section
      title="Alertas"
      meta={summary.lastUpdated ? <DataAge at={summary.lastUpdated} /> : null}
      actions={
        <Link to="/alertas" className={styles.more}>
          Ver alertas
        </Link>
      }
    >
      <AsyncContent
        state={summary}
        empty={
          <EmptyState
            title="Nenhum alerta disparado"
            description="Crie regras na watchlist para ser avisado quando preço, RSI ou volume cruzarem seus níveis."
            action={
              <Link to="/watchlist" className={buttonClass({ size: 'sm' })}>
                Criar alerta
              </Link>
            }
          />
        }
        errorTitle="Alertas indisponíveis"
      >
        {(data) => (
          <ul className={styles.feed}>
            {data.alerts.slice(0, 6).map((a) => (
              <li key={`${a.symbol}-${a.triggered_at}`} className={styles.alertRow}>
                <Link to={`/ativo/${encodeURIComponent(a.symbol)}`} className={styles.alertSymbol}>
                  {a.symbol}
                </Link>
                <span className={styles.alertMsg}>{ptBR(a.message)}</span>
                <time dateTime={a.triggered_at} className={styles.feedMeta}>
                  {formatTime(a.triggered_at)}
                </time>
              </li>
            ))}
          </ul>
        )}
      </AsyncContent>
    </Section>
  );
}

function lastClose(d: ChartData): number | null {
  for (let i = d.close.length - 1; i >= 0; i--) if (isNum(d.close[i])) return d.close[i];
  return null;
}

function lastTimestamp(d: ChartData | null): string | null {
  return d && d.timestamps.length ? d.timestamps[d.timestamps.length - 1] : null;
}

/** Variação contra o último fechamento da sessão anterior (horário de NY). */
function sessionChange(d: ChartData): number | null {
  const fmt = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' });
  const n = d.timestamps.length;
  if (n < 2) return null;
  const lastDay = fmt.format(new Date(d.timestamps[n - 1]));
  for (let i = n - 1; i >= 0; i--) {
    if (fmt.format(new Date(d.timestamps[i])) !== lastDay && isNum(d.close[i])) {
      const prev = d.close[i] as number;
      const last = lastClose(d);
      return isNum(last) && prev ? ((last - prev) / prev) * 100 : null;
    }
  }
  return null;
}
