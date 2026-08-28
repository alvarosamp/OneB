import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { usePolling } from '../hooks/usePolling';
import type {
  DashboardRow,
  DashboardSummary,
  CommodityQuote,
  EarningsEvent,
  EconomicEvent,
  FxQuote,
  GlobalNewsItem,
  NewsItem,
  PositionSummary,
} from '../types';

function fmtDate(iso: string | null) {
  if (!iso) return 'sem dados';
  return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
}

function fmtTime(iso: string | null) {
  if (!iso) return 'sem dados';
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function fmtMoney(value: number | null | undefined) {
  if (value === null || value === undefined) return '-';
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'USD' });
}

function fmtBrl(value: number | null | undefined) {
  if (value === null || value === undefined) return '-';
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function minutesSince(iso: string | null) {
  if (!iso) return null;
  return Math.round((Date.now() - new Date(iso).getTime()) / 60000);
}

function dataQuality(row: DashboardRow) {
  const age = minutesSince(row.taken_at);
  if (row.price === null || age === null) return { label: 'sem cotacao', level: 'danger' };
  if (age <= 5) return { label: 'ao vivo', level: 'good' };
  if (age <= 30) return { label: `${age} min`, level: 'warn' };
  return { label: `${age} min`, level: 'danger' };
}

function symbolCount<T extends { symbol: string }>(items: T[], symbol: string) {
  return items.filter((item) => item.symbol === symbol).length;
}

function scoreRow(row: DashboardRow, alerts: DashboardSummary['alerts'], news: NewsItem[], earnings: EarningsEvent[]) {
  let score = 50;
  const change = row.change_pct ?? 0;
  score += Math.max(-18, Math.min(18, change * 3));
  score += Math.min(12, symbolCount(news, row.symbol) * 3);
  score += Math.min(12, symbolCount(alerts, row.symbol) * 4);
  score -= symbolCount(earnings, row.symbol) > 0 ? 8 : 0;
  if (!row.price || !row.taken_at) score -= 25;
  const age = minutesSince(row.taken_at);
  if (age !== null && age > 30) score -= 10;
  return Math.max(0, Math.min(100, Math.round(score)));
}

function scoreLabel(score: number) {
  if (score >= 75) return 'forte atencao';
  if (score >= 60) return 'monitorar';
  if (score >= 40) return 'neutro';
  return 'fraco';
}

export function Dashboard() {
  const { data, error: summaryError, lastUpdated } = usePolling<DashboardSummary>('/api/dashboard-summary', 20000);
  const [econ, setEcon] = useState<EconomicEvent[]>([]);
  const [earnings, setEarnings] = useState<EarningsEvent[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [globalNews, setGlobalNews] = useState<GlobalNewsItem[]>([]);
  const [positions, setPositions] = useState<PositionSummary[]>([]);
  const [fx, setFx] = useState<FxQuote | null>(null);
  const [gold, setGold] = useState<CommodityQuote | null>(null);
  const [brlAmount, setBrlAmount] = useState('1000');

  useEffect(() => {
    api.get<EconomicEvent[]>('/api/economic-events?days_ahead=7&limit=12').then(setEcon).catch(() => {});
    api.get<EarningsEvent[]>('/api/earnings-events?days_ahead=7&limit=12').then(setEarnings).catch(() => {});
    api.get<NewsItem[]>('/api/news?limit=30').then(setNews).catch(() => {});
    api.get<GlobalNewsItem[]>('/api/global-news?limit=20').then(setGlobalNews).catch(() => {});
    api.get<PositionSummary[]>('/api/positions').then(setPositions).catch(() => {});
    api.get<FxQuote>('/api/fx/usd-brl').then(setFx).catch(() => {});
    api.get<CommodityQuote>('/api/commodities/gold').then(setGold).catch(() => {});
  }, []);

  const rows = useMemo(() => data?.rows ?? [], [data]);
  const alerts = useMemo(() => data?.alerts ?? [], [data]);

  const radarRows = useMemo(
    () =>
      rows
        .map((row) => ({
          ...row,
          score: scoreRow(row, alerts, news, earnings),
          newsCount: symbolCount(news, row.symbol),
          alertCount: symbolCount(alerts, row.symbol),
          hasEarnings: symbolCount(earnings, row.symbol) > 0,
          quality: dataQuality(row),
        }))
        .sort((a, b) => b.score - a.score),
    [alerts, earnings, news, rows],
  );

  const totalMarketValue = positions.reduce((sum, p) => sum + (p.market_value ?? 0), 0);
  const unrealizedPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0);
  const positiveRows = rows.filter((r) => (r.change_pct ?? 0) > 0).length;
  const staleRows = rows.filter((r) => {
    const age = minutesSince(r.taken_at);
    return r.price === null || age === null || age > 30;
  }).length;
  const highImpactEvents = econ.filter((e) => e.impact === 'high').length;
  const highImpactGlobalNews = globalNews.filter((n) => n.impact_score >= 40).length;

  return (
    <div className="container dashboard-container">
      <div className="page-header">
        <div>
          <p className="eyebrow">Centro de comando</p>
          <h1>Dashboard</h1>
          <p className="muted">
            Visao consolidada de precos, alertas, eventos, noticias, posicoes e qualidade dos dados.
          </p>
        </div>
        <Link className="btn-link" to="/como-usar">
          Como usar
        </Link>
      </div>

      {summaryError && <p className="data-warning" role="status">{summaryError}</p>}

      <section className="metric-grid">
        <div className="metric-card">
          <span className="metric-label">Ativos ativos</span>
          <strong>{rows.length}</strong>
          <span className="muted">{positiveRows} em alta agora</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Alertas recentes</span>
          <strong>{alerts.length}</strong>
          <span className="muted">ultimos sinais gravados</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Mundo agora</span>
          <strong>{highImpactGlobalNews}</strong>
          <span className="muted">{highImpactEvents} eventos economicos criticos</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Carteira monitorada</span>
          <strong>{fmtMoney(totalMarketValue)}</strong>
          <span className={unrealizedPnl >= 0 ? 'up' : 'down'}>{fmtMoney(unrealizedPnl)} nao realizado</span>
        </div>
      </section>

      <section className="dashboard-grid">
        <div className="panel panel-wide fx-panel">
          <div className="panel-title">
            <h2>Dolar hoje</h2>
            {fx && <span className="muted">Atualizado {fmtTime(fx.updated_at)}</span>}
          </div>
          <div className="fx-grid">
            <div>
              <span className="metric-label">USD/BRL</span>
              <strong>{fx ? fmtBrl(fx.rate) : '-'}</strong>
              <span className={fx && fx.change_pct >= 0 ? 'up' : 'down'}>
                {fx ? `${fx.change_pct >= 0 ? '+' : ''}${fx.change_pct.toFixed(2)}%` : 'sem dados'}
              </span>
            </div>
            <label className="field-label fx-converter">
              Valor em reais
              <input
                type="number"
                min="0"
                step="0.01"
                value={brlAmount}
                onChange={(e) => setBrlAmount(e.target.value)}
              />
            </label>
            <div>
              <span className="metric-label">Conversao para dolar</span>
              <strong>{fx && Number(brlAmount) >= 0 ? fmtMoney(Number(brlAmount) / fx.rate) : '-'}</strong>
              <span className="muted">{fx ? `${fmtBrl(Number(brlAmount) || 0)} / ${fx.rate.toFixed(4)}` : 'aguardando cotacao'}</span>
            </div>
            <div>
              <span className="metric-label">Ouro spot/futuro</span>
              <strong>{gold ? fmtMoney(gold.price) : '-'}</strong>
              <span className={gold && gold.change_pct >= 0 ? 'up' : 'down'}>
                {gold ? `${gold.change_pct >= 0 ? '+' : ''}${gold.change_pct.toFixed(2)}% por ${gold.unit}` : 'sem dados'}
              </span>
            </div>
            <div>
              <span className="metric-label">Ouro em reais</span>
              <strong>{gold && fx ? fmtBrl(gold.price * fx.rate) : '-'}</strong>
              <span className="muted">estimativa por {gold?.unit ?? 'onca troy'}</span>
            </div>
          </div>
        </div>

        <aside className="panel">
          <h2>Cambio e ouro</h2>
          <p className="muted">
            Para quem acompanha NASDAQ a partir do Brasil, o resultado real depende do ativo em dolar
            e tambem do cambio. O ouro ajuda a observar apetite por risco, juros reais, dolar e busca
            por protecao em momentos de estresse.
          </p>
        </aside>
      </section>

      <section className="dashboard-grid">
        <div className="panel panel-wide">
          <div className="panel-title">
            <h2>Radar de ativos</h2>
            {lastUpdated && <span className="muted">Atualizado {lastUpdated.toLocaleTimeString('pt-BR')}</span>}
          </div>
          <div className="table-scroll compact-scroll">
            <table className="table dense-table">
              <thead>
                <tr>
                  <th>Ativo</th>
                  <th>Preco</th>
                  <th>Dia</th>
                  <th>Score</th>
                  <th>Dados</th>
                  <th>Contexto</th>
                </tr>
              </thead>
              <tbody>
                {radarRows.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="muted">
                      Watchlist vazia. Adicione ativos em Watchlist &amp; Regras.
                    </td>
                  </tr>
                ) : (
                  radarRows.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <Link to={`/ativo/${row.symbol}`}>
                          <strong>{row.symbol}</strong>
                        </Link>
                        {row.label && <span className="muted block-text">{row.label}</span>}
                      </td>
                      <td>{row.price !== null ? row.price.toFixed(2) : '-'}</td>
                      <td className={(row.change_pct ?? 0) >= 0 ? 'up' : 'down'}>
                        {row.change_pct !== null ? `${row.change_pct.toFixed(2)}%` : '-'}
                      </td>
                      <td>
                        <div className="score-cell">
                          <span>{row.score}</span>
                          <meter min="0" max="100" value={row.score} />
                          <small>{scoreLabel(row.score)}</small>
                        </div>
                      </td>
                      <td>
                        <span className={`status-pill ${row.quality.level}`}>{row.quality.label}</span>
                      </td>
                      <td className="muted">
                        {row.newsCount} noticias · {row.alertCount} alertas
                        {row.hasEarnings ? ' · earnings perto' : ''}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <aside className="panel">
          <h2>Procedencia</h2>
          <ul className="source-list">
            <li>
              <strong>Finnhub</strong>
              <span>Cotacao atual, noticias e earnings</span>
            </li>
            <li>
              <strong>Yahoo/yfinance</strong>
              <span>Historico OHLCV e indicadores</span>
            </li>
            <li>
              <strong>FMP</strong>
              <span>Calendario economico</span>
            </li>
            <li>
              <strong>IA</strong>
              <span>Explica dados coletados, nao cria cotacao</span>
            </li>
          </ul>
          <div className={staleRows > 0 ? 'quality-box warn' : 'quality-box good'}>
            <strong>{staleRows > 0 ? `${staleRows} ativo(s) com dado atrasado` : 'Dados recentes'}</strong>
            <span>Use o score como triagem. Validacao final deve comparar grafico, noticia e risco.</span>
          </div>
        </aside>
      </section>

      <section className="dashboard-grid">
        <div className="panel">
          <div className="panel-title">
            <h2>Mundo agora</h2>
            <Link to="/mercado">ver macro</Link>
          </div>
          <ul className="compact-list">
            {globalNews.length === 0 ? (
              <li className="muted">Nenhuma noticia global coletada ainda.</li>
            ) : (
              globalNews.slice(0, 8).map((item, i) => (
                <li key={i}>
                  <span className={`impact-pill ${item.impact_score >= 40 ? 'danger' : item.impact_score >= 20 ? 'warn' : ''}`}>
                    {item.impact_score}
                  </span>
                  <div>
                    <a href={item.url} target="_blank" rel="noopener noreferrer">
                      {item.headline}
                    </a>
                    <span>
                      {fmtTime(item.published_at)} {item.source ? `· ${item.source}` : ''} · {item.category}
                    </span>
                  </div>
                </li>
              ))
            )}
          </ul>
        </div>

        <div className="panel">
          <div className="panel-title">
            <h2>Eventos proximos</h2>
            <Link to="/mercado">ver mercado</Link>
          </div>
          <ul className="compact-list">
            {[...econ.slice(0, 6), ...earnings.slice(0, 4)].length === 0 ? (
              <li className="muted">Nenhum evento carregado ainda.</li>
            ) : (
              <>
                {econ.slice(0, 6).map((e, i) => (
                  <li key={`econ-${i}`}>
                    <span className={`dot ${e.impact === 'high' ? 'danger' : 'warn'}`} />
                    <div>
                      <strong>{e.event_name}</strong>
                      <span>{fmtDate(e.event_date)} · {e.country} · impacto {e.impact}</span>
                    </div>
                  </li>
                ))}
                {earnings.slice(0, 4).map((e, i) => (
                  <li key={`earn-${i}`}>
                    <span className="dot info" />
                    <div>
                      <strong>{e.symbol} earnings</strong>
                      <span>{fmtDate(e.event_date)} · EPS est. {e.eps_estimate ?? '-'}</span>
                    </div>
                  </li>
                ))}
              </>
            )}
          </ul>
        </div>

        <div className="panel">
          <div className="panel-title">
            <h2>Noticias recentes</h2>
            <Link to="/mercado">ver todas</Link>
          </div>
          <ul className="compact-list">
            {news.length === 0 ? (
              <li className="muted">Nenhuma noticia coletada ainda.</li>
            ) : (
              news.slice(0, 8).map((item, i) => (
                <li key={i}>
                  <span className="mini-symbol">{item.symbol}</span>
                  <div>
                    <a href={item.url} target="_blank" rel="noopener noreferrer">
                      {item.headline}
                    </a>
                    <span>{fmtTime(item.published_at)} {item.source ? `· ${item.source}` : ''}</span>
                  </div>
                </li>
              ))
            )}
          </ul>
        </div>
      </section>

      <section className="dashboard-grid">
        <div className="panel">
          <div className="panel-title">
            <h2>Posicoes</h2>
            <Link to="/posicoes">gerenciar</Link>
          </div>
          <div className="table-scroll compact-scroll">
            <table className="table dense-table">
              <thead>
                <tr>
                  <th>Ativo</th>
                  <th>Qtd.</th>
                  <th>Valor</th>
                  <th>P&amp;L</th>
                </tr>
              </thead>
              <tbody>
                {positions.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="muted">
                      Nenhuma posicao registrada.
                    </td>
                  </tr>
                ) : (
                  positions.slice(0, 8).map((p) => (
                    <tr key={p.symbol}>
                      <td>{p.symbol}</td>
                      <td>{p.quantity.toFixed(4)}</td>
                      <td>{fmtMoney(p.market_value)}</td>
                      <td className={(p.unrealized_pnl ?? 0) >= 0 ? 'up' : 'down'}>{fmtMoney(p.unrealized_pnl)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <div className="panel-title">
            <h2>Alertas recentes</h2>
            <Link to="/alertas">filtrar</Link>
          </div>
          <ul className="compact-list">
            {alerts.length === 0 ? (
              <li className="muted">Nenhum alerta disparado ainda.</li>
            ) : (
              alerts.slice(0, 8).map((a, i) => (
                <li key={i}>
                  <span className="mini-symbol">{a.symbol}</span>
                  <div>
                    <strong>{a.message}</strong>
                    <span>
                      {fmtTime(a.triggered_at)}
                      {a.delivered_telegram ? ' · Telegram enviado' : ''}
                    </span>
                  </div>
                </li>
              ))
            )}
          </ul>
        </div>
      </section>
    </div>
  );
}
