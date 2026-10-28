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
import { CHART_ASSETS, CHART_ASSET_GROUPS } from '../content/chartAssets';
import { chartPath, TIMEFRAMES, type Timeframe } from '../lib/timeframes';
import { formatDateTime, formatLongDate, formatNumber, formatPrice, formatSigned, formatTime, isNum, priceDigits } from '../lib/format';
import { ptBR } from '../lib/text';
import type { RadarRow } from '../hooks/useRadar';
import type {
  PlanScoreboard,
  ChartData,
  DailyMarketSummary,
  DashboardSummary,
  EarningsEvent,
  EconomicEvent,
  GlobalNewsItem,
  LearningState,
  RegimeReport,
  TechnicalAnalysis,
  NextSession,
  TrendReadings,
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
      <ContextBlock />
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
  const [assetId, setAssetId] = useQueryTab(CHART_ASSETS.map((a) => a.id), 'nasdaq', 'ativo');
  const asset = CHART_ASSETS.find((a) => a.id === assetId)!;
  const [tfId, setTfId] = useQueryTab<HeroTf>(['1D', '5D', '1M'], '5D', 'tf');
  const tf = HERO_TFS.find((t) => t.id === tfId) as Timeframe;
  const chart = useApi<ChartData>(chartPath(asset.symbol, tf), { pollMs: 60_000, isEmpty: (d) => d.close.length === 0 });
  const last = chart.data ? lastClose(chart.data) : null;
  const dayChange = chart.data ? sessionChange(chart.data) : null;

  return (
    <section className={styles.chartArea} aria-label={`Gráfico de ${asset.label}`}>
      <label className={styles.assetPicker}>
        Ativo do gráfico
        <select value={assetId} onChange={(e) => setAssetId(e.target.value as typeof assetId)}>
          {CHART_ASSET_GROUPS.map((group) => (
            <optgroup key={group} label={group}>
              {CHART_ASSETS.filter((a) => a.group === group).map((a) => <option key={a.id} value={a.id}>{a.option}</option>)}
            </optgroup>
          ))}
        </select>
      </label>
      <div className={styles.chartHeader}>
        <div className={styles.quote}>
          <Link to={`/ativo/${encodeURIComponent(asset.symbol)}`} className={styles.symbol}>
            {asset.label} <span>{asset.symbol}</span>
          </Link>
          <span className={styles.bigPrice}>{isNum(last) ? formatNumber(last, priceDigits(last)) : chart.status === 'loading' ? <Skeleton width={120} height={24} /> : '—'}</span>
          {isNum(last) && <ChangeText value={dayChange} className={styles.bigChange} />}
          {chart.lastUpdated && <DataAge at={lastTimestamp(chart.data)} staleAfterMin={30} refreshError={chart.data ? chart.error : null} prefix="último candle" />}
        </div>
        <Tabs items={HERO_TFS.map((t) => ({ value: t.id as HeroTf, label: t.label }))} value={tfId} onChange={setTfId} label="Período do gráfico" variant="segmented" />
      </div>
      <AsyncContent
        state={chart}
        loading={<Skeleton height={380} />}
        empty={<EmptyState center title={`Sem candles para ${asset.label} neste período`} description={chart.error ?? 'O provedor de dados não retornou histórico. Tente outro período.'} />}
        errorTitle="Não foi possível carregar o gráfico"
      >
        {(data) => <ChartPanel key={asset.symbol} data={data} timeframe={tf} panels={['volume']} height={340} label={asset.label} />}
      </AsyncContent>
      <p className={styles.readNote}>{asset.note} A leitura do dia abaixo acompanha a Nasdaq.</p>
    </section>
  );
}

function DailyRead() {
  const regime = useApi<RegimeReport>('/api/regime/NASDAQ', { pollMs: 10 * 60_000 });
  const tech = useApi<TechnicalAnalysis>(`/api/technical/analysis/${encodeURIComponent(HERO_SYMBOL)}?period=5d&interval=15m`, { pollMs: 5 * 60_000 });
  const summary = useApi<DailyMarketSummary>('/api/reports/daily-summary', { pollMs: 5 * 60_000 });

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
            {summary.data && <DataAge at={summary.data.data_checked_at} prefix="resumo: fonte consultada" staleAfterMin={10} refreshError={summary.error ?? (summary.data.data_status === 'cached' || summary.data.data_status === 'stale' ? 'O resumo usa preços anteriores.' : null)} refreshing={summary.refreshing} />}
          </>
        }
      />
      {(regime.status === 'error' || tech.status === 'error') && (
        <p className={styles.partial}>Parte dos dados não carregou: {regime.error ?? tech.error}</p>
      )}
    </aside>
  );
}

/** Contexto de médio prazo e estudo: tendência de 1/3/12 meses e a próxima aula. */
function NextSessionBlock() {
  const data = useApi<NextSession>('/api/analysis/next-session', { pollMs: 30 * 60_000, isEmpty: (d) => d.assets.every((a) => !a.forecast) });
  return (
    <Section
      title="Próximo pregão"
      meta="quanto deve mexer (não para onde)"
      actions={
        <Link to="/analise?tab=ativo" className={styles.more}>
          Ver ativo
        </Link>
      }
    >
      <AsyncContent state={data} loading={<SkeletonLines lines={4} />} empty={<EmptyState title="Sem previsão agora" description="O histórico diário ainda não carregou." />} errorTitle="Previsão indisponível">
        {(d) => (
          <ul className={styles.feed}>
            {d.assets
              .filter((a) => a.forecast)
              .map((a) => {
                const f = a.forecast!;
                return (
                  <li key={a.key} className={styles.pairRow}>
                    <span className={styles.eventBody}>
                      <span className={styles.eventTitle}>{a.label}</span>
                      <span className={styles.feedMeta}>
                        8 em 10 dias: {formatNumber(f.low80_pct, 2)}% a {formatNumber(f.high80_pct, 2)}%{f.event ? ` · ${f.event}` : ''}
                      </span>
                    </span>
                    <Badge tone={f.event ? 'warning' : 'neutral'}>{formatNumber(f.expected_pct, 2)}%</Badge>
                  </li>
                );
              })}
            {d.events.slice(0, 3).map((e) => (
              <li key={e.event_name + e.event_date} className={styles.pairRow}>
                <span className={styles.eventBody}>
                  <span className={styles.eventTitle}>{e.event_name}</span>
                  <span className={styles.feedMeta}>
                    {new Date(e.event_date).toLocaleString('pt-BR', { weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', timeZone: 'America/Sao_Paulo' })}
                    {e.assets.length ? ` · até ${formatNumber(Math.max(...e.assets.map((x) => x.post30 ?? 0)), 1)}x o movimento normal em 30 min` : ''}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </AsyncContent>
    </Section>
  );
}

const PLAN_RESULT: Record<string, string> = { hit: 'bateu o alvo', stop: 'stop antes', expired: 'expirou', open: 'em andamento' };

/** Plano das 10:30 (placar ao vivo, regra fixa): o estado do alvo 2R de cada plano do dia. */
function PlanTodayBlock() {
  const data = useApi<PlanScoreboard>('/api/analysis/plan-scoreboard', {
    pollMs: 15 * 60_000,
    isEmpty: (d) => Object.values(d.assets).every((a) => !a.live || a.live.rows.length === 0),
  });
  return (
    <Section
      title="Plano das 10:30"
      meta="placar ao vivo, regra fixa (não é sinal)"
      actions={
        <span className={styles.planLinks}>
          <Link to="/analise?tab=conta" className={styles.more}>
            Quanto operar
          </Link>
          <Link to="/analise?tab=confianca" className={styles.more}>
            Placar
          </Link>
        </span>
      }
    >
      <AsyncContent
        state={data}
        loading={<SkeletonLines lines={4} />}
        empty={<EmptyState title="Nenhum plano ao vivo ainda" description="Todo dia útil às 10:30 de Brasília o OneB registra um plano de compra e um de venda." />}
        errorTitle="Placar indisponível"
      >
        {(d) => (
          <ul className={styles.feed}>
            {Object.entries(d.assets).flatMap(([key, a]) => {
              const rows = a.live?.rows ?? [];
              const last = rows.reduce((m, r) => (r.date > m ? r.date : m), '');
              return rows
                .filter((r) => r.date === last)
                .map((r) => (
                  <li key={`${key}-${r.date}-${r.direction}`} className={styles.pairRow}>
                    <span className={styles.eventBody}>
                      <span className={styles.eventTitle}>
                        {a.label} · {r.direction === 'long' ? 'compra' : 'venda'}
                      </span>
                      <span className={styles.feedMeta}>
                        {r.date.split('-').reverse().slice(0, 2).join('/')}
                        {r.stop_distance != null ? ` · stop de ${formatNumber(r.stop_distance, r.stop_distance >= 0.1 ? 2 : 5)}` : ''} · TP1 {PLAN_RESULT[r.results['1']]}
                      </span>
                    </span>
                    <Badge tone={r.results['2'] === 'hit' ? 'positive' : r.results['2'] === 'open' ? 'neutral' : 'negative'}>2R: {PLAN_RESULT[r.results['2']]}</Badge>
                  </li>
                ));
            })}
          </ul>
        )}
      </AsyncContent>
    </Section>
  );
}

function ContextBlock() {
  const trend = useApi<TrendReadings>('/api/trend/readings', { pollMs: 60 * 60_000, isEmpty: (d) => d.assets.length === 0 });
  const learning = useApi<LearningState>('/api/lms/learning-state');
  const next = learning.data?.last_lesson
    ? { slug: learning.data.last_lesson.course_slug, id: learning.data.last_lesson.lesson_id, title: learning.data.last_lesson.lesson_title, verb: 'Continuar' }
    : learning.data?.recommendation
      ? { slug: learning.data.recommendation.course_slug, id: learning.data.recommendation.lesson_id, title: learning.data.recommendation.lesson_title, verb: 'Próxima aula' }
      : null;
  const asEvidence = trend.data?.evidence.as_evidence ?? false;
  return (
    <div className={styles.feeds}>
      <NextSessionBlock />
      <PlanTodayBlock />
      <Section
        title="Tendência"
        meta={asEvidence ? '1, 3 e 12 meses, com evidência' : '1, 3 e 12 meses, descrição do preço'}
        actions={
          <Link to="/analise?tab=tendencia" className={styles.more}>
            Ver tendência
          </Link>
        }
      >
        <AsyncContent state={trend} loading={<SkeletonLines lines={4} />} empty={<EmptyState title="Sem leitura de tendência" description="O histórico diário ainda não carregou." />} errorTitle="Tendência indisponível">
          {(d) => (
            <ul className={styles.feed}>
              {d.assets
                .filter((a) => a.available)
                .map((a) => (
                  <li key={a.key} className={styles.pairRow}>
                    <span className={styles.eventBody}>
                      <span className={styles.eventTitle}>{a.label}</span>
                      <span className={styles.feedMeta}>{a.horizons?.map((h) => `${h.label} ${h.direction}`).join(' · ')}</span>
                    </span>
                    <Badge tone={a.agreement === 'todos em alta' ? 'positive' : a.agreement === 'todos em baixa' ? 'negative' : 'neutral'}>{a.agreement}</Badge>
                  </li>
                ))}
            </ul>
          )}
        </AsyncContent>
      </Section>
      <Section
        title="Academia"
        meta="seu próximo passo"
        actions={
          <Link to="/academia" className={styles.more}>
            Ver trilhas
          </Link>
        }
      >
        {next ? (
          <div className={styles.eventBody}>
            <span className={styles.eventTitle}>{ptBR(next.title)}</span>
            <span className={styles.feedMeta}>Termine a aula antes de operar o que ela ensina. O Laboratório deixa você treinar sem risco.</span>
            <Link to={`/aulas/${next.slug}?aula=${next.id}`} className={buttonClass({ size: 'sm', variant: 'primary' })}>
              {next.verb}
            </Link>
          </div>
        ) : (
          <EmptyState title="Comece pela Academia" description="Fundamentos, risco e como avaliar um sinal, com prática no Laboratório." />
        )}
      </Section>
    </div>
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
      detail: [
        e.country,
        e.forecast && `proj. ${e.forecast}`,
        e.previous && `ant. ${e.previous}`,
        // Volatilidade típica medida no estudo calendar_v1 (30 min depois da divulgação).
        e.risk && `volatilidade típica ${e.risk.assets.map((a) => `${a.label} ${formatNumber(a.post30 ?? null, 1)}x`).join(', ')}`,
      ]
        .filter(Boolean)
        .join(', '),
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
