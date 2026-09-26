import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../api/client';
import { usePolling } from '../hooks/usePolling';

interface RegimeFactor {
  name: string;
  impact: number | null;
  evidence: string;
}

interface LocalRegime {
  label: string;
  score: number;
  factors: RegimeFactor[];
}

interface CrossAssetRow {
  key: string;
  name: string;
  correlation_30d: number;
  relevance: 'ALTA' | 'MEDIA' | 'BAIXA';
  direction: 'CONFIRMANDO' | 'DIVERGINDO' | null;
  change_pct_latest: number | null;
}

interface RegimeReport {
  symbol: string;
  local_regime: LocalRegime | null;
  macro_context: 'POSITIVO' | 'NEUTRO' | 'NEGATIVO';
  cross_asset_relevance: CrossAssetRow[];
}

interface MacroInstrument {
  key: string;
  symbol: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  taken_at: string | null;
  context: string | null;
  trend: TrendAnalysis | null;
}

interface TrendAnalysis {
  direction: 'ALTA FORTE' | 'ALTA' | 'LATERAL' | 'BAIXA' | 'BAIXA FORTE';
  score: number;
  strength: 'FORTE' | 'MODERADA' | 'FRACA' | 'INDEFINIDA';
  adx14: number | null;
  change_5d: number | null;
  change_20d: number | null;
  change_60d: number | null;
  change_unit: '%' | 'bps';
  last: number;
  ema20: number;
  ema50: number;
  as_of: string;
  age_days: number;
}

interface CorrelationPair {
  left: string;
  right: string;
  correlation: number;
  observations: number;
}

interface CorrelationWindow {
  sessions: number;
  minimum_observations: number;
  matrix: Array<{ key: string; values: Record<string, number | null> }>;
  strongest_positive: CorrelationPair[];
  strongest_negative: CorrelationPair[];
}

interface RelationshipDynamic {
  left: string;
  right: string;
  correlation_20d: number;
  correlation_60d: number;
  delta: number;
  strength_delta: number;
  status: 'INVERSAO' | 'FORTALECENDO' | 'ENFRAQUECENDO' | 'ESTAVEL';
}

interface LeadLagCandidate {
  leader: string;
  follower: string;
  lag_sessions: number;
  correlation: number;
  contemporaneous_correlation: number | null;
  improvement: number;
  observations: number;
}

interface LeadLagValidation {
  leader: string;
  follower: string;
  lag_sessions: number;
  observations_days: number;
  persistence_pct: number;
  average_correlation: number;
  last_seen: string;
  status: 'RECORRENTE' | 'OBSERVACAO';
}

interface NewsContext {
  window_start: string;
  window_end: string;
  article_count: number;
  high_impact_count: number;
  impact_sum: number;
  average_impact: number | null;
  maximum_impact: number | null;
  mean_sentiment: number | null;
  sentiment_observations: number;
  sentiment_coverage_pct: number;
  theme_counts: Record<string, number>;
  top_headlines: Array<{
    headline: string;
    source: string;
    impact_score: number;
    sentiment_score: number | null;
    published_at: string;
    url: string;
  }>;
}

interface NewsMarketCorrelation {
  factor_type: 'INTENSIDADE' | 'SENTIMENTO' | 'TEMA';
  factor: string;
  asset: string;
  target: 'MAGNITUDE' | 'DIRECAO';
  correlation: number;
  observations: number;
  direction: 'POSITIVA' | 'NEGATIVA';
  status: 'EXPLORATORIO';
}

interface NewsMarketAnalysis {
  method: string;
  minimum_observations: number;
  available_forward_pairs: number;
  status: 'PRONTO' | 'COLETANDO_HISTORICO';
  correlations: NewsMarketCorrelation[];
  warnings: string[];
}

interface MacroHistoryStatus {
  days_recorded: number;
  latest: {
    snapshot_date: string;
    captured_at: string;
    coverage_pct: number;
    fresh_count: number;
    stale_count: number;
    missing_count: number;
  } | null;
  lead_lag_validation: LeadLagValidation[];
  latest_news_context?: NewsContext | null;
  news_market_analysis?: NewsMarketAnalysis;
}

interface MacroOverview {
  instruments: MacroInstrument[];
  trend_watchlist: MacroInstrument[];
  correlation_windows?: Partial<Record<'20' | '60', CorrelationWindow>>;
  relationship_dynamics?: RelationshipDynamic[];
  lead_lag_candidates?: LeadLagCandidate[];
  history_status?: MacroHistoryStatus;
  nasdaq_cross_asset_relevance: CrossAssetRow[];
}

const REGIME_CLASS: Record<string, string> = {
  'STRONG BULL': 'up',
  BULL: 'up',
  NEUTRAL: '',
  BEAR: 'down',
  'STRONG BEAR': 'down',
};

function fmtPct(value: number | null) {
  if (value === null || value === undefined) return '-';
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function fmtTrendChange(value: number | null, unit: '%' | 'bps') {
  if (value === null || value === undefined) return '-';
  return `${value >= 0 ? '+' : ''}${value.toFixed(unit === 'bps' ? 1 : 2)} ${unit}`;
}

function trendClass(direction: TrendAnalysis['direction']) {
  if (direction.startsWith('ALTA')) return 'up';
  if (direction.startsWith('BAIXA')) return 'down';
  return '';
}

function changeClass(value: number | null) {
  if (value === null || value === undefined) return 'muted';
  return value >= 0 ? 'up' : 'down';
}

function correlationStyle(value: number | null) {
  if (value === null) return undefined;
  const opacity = 0.08 + Math.abs(value) * 0.36;
  return {
    backgroundColor: value >= 0 ? `rgba(38, 132, 255, ${opacity})` : `rgba(239, 83, 80, ${opacity})`,
  };
}

function newsFactorLabel(value: string) {
  return value.replaceAll('_', ' ').toLocaleLowerCase('pt-BR');
}

export function Regime() {
  const [symbol, setSymbol] = useState('NASDAQ');
  const [symbolInput, setSymbolInput] = useState('NASDAQ');
  const [report, setReport] = useState<RegimeReport | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [correlationWindow, setCorrelationWindow] = useState<'20' | '60'>('60');
  const { data: macro, lastUpdated } = usePolling<MacroOverview>('/api/regime/macro', 60000);
  const selectedCorrelations = macro?.correlation_windows?.[correlationWindow];

  async function loadReport(targetSymbol: string) {
    setReportError(null);
    try {
      const result = await api.get<RegimeReport>(`/api/regime/${encodeURIComponent(targetSymbol)}`);
      setReport(result);
    } catch (err) {
      setReport(null);
      setReportError(err instanceof Error ? err.message : 'Erro ao buscar regime');
    }
  }

  useEffect(() => {
    loadReport(symbol);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const next = symbolInput.trim().toUpperCase();
    if (!next) return;
    setSymbol(next);
    loadReport(next);
  }

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <p className="eyebrow">Regime de mercado</p>
          <h1>Regime Engine</h1>
          <p className="muted">
            Estado local (tendência/momentum/volatilidade/estrutura) de um ativo, combinado com o
            contexto macro/cross-asset — leitura determinística, sem IA envolvida no cálculo.
          </p>
        </div>
      </div>

      <section className="panel">
        <form onSubmit={handleSubmit} className="inline-form">
          <input
            value={symbolInput}
            onChange={(e) => setSymbolInput(e.target.value)}
            placeholder="Ex: NASDAQ, AAPL, GOLD, SP500"
          />
          <button type="submit">Ver regime</button>
        </form>

        {reportError && <p className="muted">{reportError}</p>}

        {report && (
          <div className="regime-card">
            <div className="regime-card-header">
              <h2>{report.symbol}</h2>
              {report.local_regime ? (
                <span className={`pill ${REGIME_CLASS[report.local_regime.label] ?? ''}`}>
                  {report.local_regime.label} ({report.local_regime.score})
                </span>
              ) : (
                <span className="muted">Sem histórico suficiente</span>
              )}
              <span className={`pill ${report.macro_context === 'POSITIVO' ? 'up' : report.macro_context === 'NEGATIVO' ? 'down' : ''}`}>
                Macro: {report.macro_context}
              </span>
            </div>

            {report.local_regime && report.local_regime.factors.length > 0 && (
              <ul className="compact-list">
                {report.local_regime.factors.map((f, i) => (
                  <li key={i}>
                    <span className="mini-symbol">{f.impact !== null ? `${f.impact > 0 ? '+' : ''}${f.impact}` : '-'}</span>
                    <div>
                      <strong>{f.name}</strong>
                      <span>{f.evidence}</span>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {report.cross_asset_relevance.length > 0 && (
              <div className="table-scroll compact-scroll">
                <table className="table dense-table">
                  <thead>
                    <tr>
                      <th>Instrumento</th>
                      <th>Correlação 30d</th>
                      <th>Relevância</th>
                      <th>Direção</th>
                      <th>Variação recente</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.cross_asset_relevance.map((row) => (
                      <tr key={row.key}>
                        <td>{row.name}</td>
                        <td>{row.correlation_30d.toFixed(2)}</td>
                        <td>{row.relevance}</td>
                        <td>{row.direction ?? '-'}</td>
                        <td className={(row.change_pct_latest ?? 0) >= 0 ? 'up' : 'down'}>
                          {fmtPct(row.change_pct_latest)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </section>

      <section className="panel">
        <div className="panel-title">
          <div>
            <p className="eyebrow">Sua carteira macro</p>
            <h2>Radar de tendências</h2>
            <p className="muted">Direção por EMA20/EMA50, força por ADX e movimento em três horizontes.</p>
          </div>
          {lastUpdated && <span className="muted">Atualizado {lastUpdated.toLocaleTimeString('pt-BR')}</span>}
        </div>
        <div className="table-scroll compact-scroll">
          <table className="table dense-table">
            <thead>
              <tr>
                <th>Instrumento</th>
                <th>Tendência</th>
                <th>Força</th>
                <th>5 sessões</th>
                <th>20 sessões</th>
                <th>60 sessões</th>
                <th>Dado</th>
              </tr>
            </thead>
            <tbody>
              {!macro || (macro.trend_watchlist ?? []).length === 0 ? (
                <tr>
                  <td colSpan={7} className="muted">
                    Ainda sem snapshots — aguarde o próximo ciclo do coletor macro.
                  </td>
                </tr>
              ) : (
                (macro.trend_watchlist ?? []).map((inst) => {
                  const trend = inst.trend;
                  return (
                    <tr key={inst.key} className="trend-row" onClick={() => {
                      setSymbol(inst.key);
                      setSymbolInput(inst.key);
                      loadReport(inst.key);
                    }}>
                      <td>
                        <strong>{inst.name}</strong>
                        <span className="table-subline">{inst.symbol} · {inst.context}</span>
                      </td>
                      <td>
                        {trend ? <span className={`pill ${trendClass(trend.direction)}`}>{trend.direction} ({trend.score})</span> : '-'}
                      </td>
                      <td>{trend ? `${trend.strength}${trend.adx14 !== null ? ` · ADX ${trend.adx14}` : ''}` : '-'}</td>
                      <td className={changeClass(trend?.change_5d ?? null)}>
                        {trend ? fmtTrendChange(trend.change_5d, trend.change_unit) : '-'}
                      </td>
                      <td className={changeClass(trend?.change_20d ?? null)}>
                        {trend ? fmtTrendChange(trend.change_20d, trend.change_unit) : '-'}
                      </td>
                      <td className={changeClass(trend?.change_60d ?? null)}>
                        {trend ? fmtTrendChange(trend.change_60d, trend.change_unit) : '-'}
                      </td>
                      <td className={trend && trend.age_days > 3 ? 'down' : 'muted'}>
                        {trend ? `${trend.age_days}d atrás` : '-'}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
        <p className="muted small-note">
          Juros são exibidos em pontos-base; índices, commodities e moedas em percentual. Clique em uma linha para ver os fatores detalhados.
        </p>
      </section>

      <section className="panel">
        <div className="panel-title correlation-panel-title">
          <div>
            <p className="eyebrow">Visão cross-asset</p>
            <h2>Correlação móvel</h2>
            <p className="muted">Como os movimentos diários dos ativos estão se relacionando, sem presumir relações fixas.</p>
          </div>
          <div className="segmented-control" role="group" aria-label="Janela de correlação">
            {(['20', '60'] as const).map((window) => (
              <button
                key={window}
                type="button"
                className={`segmented-option${correlationWindow === window ? ' active' : ''}`}
                onClick={() => setCorrelationWindow(window)}
              >
                {window} sessões
              </button>
            ))}
          </div>
        </div>

        {!selectedCorrelations ? (
          <p className="muted">Ainda não há histórico comum suficiente para calcular as correlações.</p>
        ) : (
          <>
            <div className="correlation-highlights">
              <div>
                <strong>Maiores convergências</strong>
                {selectedCorrelations.strongest_positive.slice(0, 3).map((pair) => (
                  <span key={`${pair.left}-${pair.right}`}>
                    {pair.left} × {pair.right} <b className="up">+{pair.correlation.toFixed(2)}</b>
                  </span>
                ))}
              </div>
              <div>
                <strong>Maiores divergências</strong>
                {selectedCorrelations.strongest_negative.slice(0, 3).map((pair) => (
                  <span key={`${pair.left}-${pair.right}`}>
                    {pair.left} × {pair.right} <b className="down">{pair.correlation.toFixed(2)}</b>
                  </span>
                ))}
              </div>
            </div>
            <div className="table-scroll correlation-scroll">
              <table className="table dense-table correlation-matrix">
                <thead>
                  <tr>
                    <th>Ativo</th>
                    {selectedCorrelations.matrix.map((column) => <th key={column.key}>{column.key}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {selectedCorrelations.matrix.map((row) => (
                    <tr key={row.key}>
                      <th>{row.key}</th>
                      {selectedCorrelations.matrix.map((column) => {
                        const value = row.values[column.key];
                        return (
                          <td
                            key={column.key}
                            style={correlationStyle(value)}
                            title={`${row.key} × ${column.key}: ${value === null ? 'dados insuficientes' : value.toFixed(2)}`}
                          >
                            {value === null ? '-' : value.toFixed(2)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="relationship-intelligence">
              <div>
                <strong>Mudanças de relação</strong>
                <p className="muted">Comparação entre as janelas de 20 e 60 sessões.</p>
                {(macro?.relationship_dynamics ?? []).filter((row) => row.status !== 'ESTAVEL').slice(0, 5).map((row) => (
                  <span key={`${row.left}-${row.right}`}>
                    <b>{row.left} × {row.right}</b>
                    <em className={row.status === 'INVERSAO' ? 'down' : ''}>{row.status}</em>
                    <small>{row.correlation_60d.toFixed(2)} → {row.correlation_20d.toFixed(2)}</small>
                  </span>
                ))}
                {(macro?.relationship_dynamics ?? []).filter((row) => row.status !== 'ESTAVEL').length === 0 && (
                  <span className="muted">Nenhuma mudança material detectada.</span>
                )}
              </div>
              <div>
                <strong>Antecedências exploratórias</strong>
                <p className="muted">Relações defasadas que superam a correlação simultânea.</p>
                {(macro?.lead_lag_candidates ?? []).slice(0, 5).map((row) => (
                  <span key={`${row.leader}-${row.follower}-${row.lag_sessions}`}>
                    <b>{row.leader} → {row.follower}</b>
                    <em>{row.lag_sessions} sessões</em>
                    <small>corr. {row.correlation.toFixed(2)} · ganho {row.improvement.toFixed(2)}</small>
                  </span>
                ))}
                {(macro?.lead_lag_candidates ?? []).length === 0 && (
                  <span className="muted">Nenhuma antecedência robusta nesta janela.</span>
                )}
              </div>
            </div>
            <div className="macro-history-status">
              <div>
                <span>Histórico persistido</span>
                <strong>{macro?.history_status?.days_recorded ?? 0} pregões</strong>
              </div>
              <div>
                <span>Cobertura mais recente</span>
                <strong>{macro?.history_status?.latest ? `${macro.history_status.latest.coverage_pct.toFixed(1)}%` : 'Aguardando coleta'}</strong>
                {macro?.history_status?.latest && (
                  <small>
                    {macro.history_status.latest.fresh_count} frescos · {macro.history_status.latest.stale_count} defasados · {macro.history_status.latest.missing_count} ausentes
                  </small>
                )}
              </div>
              <div>
                <span>Antecedências recorrentes</span>
                <strong>
                  {(macro?.history_status?.lead_lag_validation ?? []).filter((row) => row.status === 'RECORRENTE').length}
                </strong>
                <small>Exige 5+ dias e presença em pelo menos 30% das coletas.</small>
              </div>
            </div>
            <div className="news-market-panel">
              <div className="news-market-heading">
                <div>
                  <p className="eyebrow">Contexto informacional</p>
                  <h3>Notícias × mercado</h3>
                </div>
                <span className={`pill ${macro?.history_status?.news_market_analysis?.status === 'PRONTO' ? 'up' : ''}`}>
                  {macro?.history_status?.news_market_analysis?.status === 'PRONTO' ? 'Amostra disponível' : 'Coletando histórico'}
                </span>
              </div>
              <div className="news-market-summary">
                <div>
                  <span>Notícias nas últimas 24h</span>
                  <strong>{macro?.history_status?.latest_news_context?.article_count ?? 0}</strong>
                  <small>{macro?.history_status?.latest_news_context?.high_impact_count ?? 0} de alto impacto</small>
                </div>
                <div>
                  <span>Impacto médio</span>
                  <strong>{macro?.history_status?.latest_news_context?.average_impact?.toFixed(1) ?? '-'}</strong>
                  <small>Intensidade, não direção</small>
                </div>
                <div>
                  <span>Cobertura de sentimento</span>
                  <strong>{(macro?.history_status?.latest_news_context?.sentiment_coverage_pct ?? 0).toFixed(1)}%</strong>
                  <small>Direção só é testada quando há score</small>
                </div>
              </div>
              <div className="news-market-columns">
                <div>
                  <strong>Temas dominantes</strong>
                  {Object.entries(macro?.history_status?.latest_news_context?.theme_counts ?? {})
                    .sort((left, right) => right[1] - left[1])
                    .slice(0, 6)
                    .map(([theme, count]) => (
                      <span key={theme}><b>{newsFactorLabel(theme)}</b><em>{count} notícia{count === 1 ? '' : 's'}</em></span>
                    ))}
                  {Object.keys(macro?.history_status?.latest_news_context?.theme_counts ?? {}).length === 0 && (
                    <span className="muted">Nenhum tema classificado na coleta mais recente.</span>
                  )}
                </div>
                <div>
                  <strong>Relações prospectivas</strong>
                  {(macro?.history_status?.news_market_analysis?.correlations ?? []).slice(0, 6).map((row) => (
                    <span key={`${row.factor_type}-${row.factor}-${row.asset}`}>
                      <b>{newsFactorLabel(row.factor)} → {row.asset}</b>
                      <em className={row.correlation >= 0 ? 'up' : 'down'}>{row.correlation >= 0 ? '+' : ''}{row.correlation.toFixed(2)}</em>
                      <small>{row.target === 'MAGNITUDE' ? 'magnitude' : 'direção'} · {row.observations} pares</small>
                    </span>
                  ))}
                  {(macro?.history_status?.news_market_analysis?.correlations ?? []).length === 0 && (
                    <span className="muted">
                      {macro?.history_status?.news_market_analysis?.available_forward_pairs ?? 0}/
                      {macro?.history_status?.news_market_analysis?.minimum_observations ?? 20} pares notícia → próximo pregão.
                    </span>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
        <p className="muted small-note">
          Azul indica movimento conjunto; vermelho, movimento inverso. Correlação não implica causalidade e pode mudar entre regimes.
          Para juros, usamos a mudança diária do yield; para os demais ativos, o retorno diário. Antecedências são hipóteses exploratórias,
          sujeitas a múltiplos testes e validação fora da amostra. Notícias do dia são comparadas somente ao próximo pregão: impacto e temas
          com a magnitude do movimento; sentimento, quando disponível, com a direção.
        </p>
      </section>
    </div>
  );
}
