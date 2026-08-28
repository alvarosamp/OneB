import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { usePolling } from '../hooks/usePolling';
import type { EarningsEvent, EconomicEvent, GlobalNewsItem, NewsItem } from '../types';

function fmtDateTime(iso: string) {
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function Mercado() {
  const { data: news, lastUpdated } = usePolling<NewsItem[]>('/api/news?limit=40', 60000);
  const { data: globalNews, lastUpdated: globalLastUpdated } = usePolling<GlobalNewsItem[]>(
    '/api/global-news?limit=60',
    60000,
  );
  const [econ, setEcon] = useState<EconomicEvent[]>([]);
  const [earnings, setEarnings] = useState<EarningsEvent[]>([]);
  const [calendarError, setCalendarError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<EconomicEvent[]>('/api/economic-events?days_ahead=14&limit=50'),
      api.get<EarningsEvent[]>('/api/earnings-events?days_ahead=14&limit=50'),
    ])
      .then(([events, upcomingEarnings]) => {
        setEcon(events);
        setEarnings(upcomingEarnings);
        setCalendarError(null);
      })
      .catch((err: unknown) => {
        setCalendarError(err instanceof Error ? err.message : 'Não foi possível carregar a agenda de mercado.');
      });
  }, []);

  return (
    <div className="container dashboard-container">
      <div className="page-header">
        <div>
          <p className="eyebrow">Monitor macro</p>
          <h1>Painel de Mercado</h1>
          <p className="muted">
            Noticias globais, eventos economicos, earnings e manchetes por ativo em um so lugar.
          </p>
        </div>
      </div>

      <section className="panel">
        <div className="panel-title">
          <h2>Noticias do mundo e macro</h2>
          {globalLastUpdated && <span className="muted">Atualizado {globalLastUpdated.toLocaleTimeString('pt-BR')}</span>}
        </div>
        <ul className="compact-list">
          {!globalNews || globalNews.length === 0 ? (
            <li className="muted">Nenhuma noticia global coletada ainda.</li>
          ) : (
            globalNews.map((n, i) => (
              <li key={i}>
                <span className={`impact-pill ${n.impact_score >= 40 ? 'danger' : n.impact_score >= 20 ? 'warn' : ''}`}>
                  {n.impact_score}
                </span>
                <div>
                  <a href={n.url} target="_blank" rel="noopener noreferrer">
                    {n.headline}
                  </a>
                  <span>
                    {fmtDateTime(n.published_at)} {n.source ? `· ${n.source}` : ''} · {n.category}
                  </span>
                </div>
              </li>
            ))
          )}
        </ul>
      </section>

      {(globalNews === null || news === null || calendarError) && (
        <p className="data-warning" role="status">
          {calendarError ?? 'Parte dos dados de mercado está indisponível. A página tentará atualizar novamente.'}
        </p>
      )}

      <section className="panel">
        <div className="panel-title">
          <h2>Noticias por ativo</h2>
          {lastUpdated && <span className="muted">Atualizado {lastUpdated.toLocaleTimeString('pt-BR')}</span>}
        </div>
        <ul className="compact-list">
          {!news || news.length === 0 ? (
            <li className="muted">Nenhuma noticia coletada ainda.</li>
          ) : (
            news.map((n, i) => (
              <li key={i}>
                <span className="mini-symbol">{n.symbol}</span>
                <div>
                  <a href={n.url} target="_blank" rel="noopener noreferrer">
                    {n.headline}
                  </a>
                  <span>
                    {fmtDateTime(n.published_at)} {n.source ? `· ${n.source}` : ''}
                  </span>
                </div>
              </li>
            ))
          )}
        </ul>
      </section>

      <section className="panel">
        <h2>Calendario economico (proximos dias)</h2>
        <div className="table-scroll compact-scroll">
          <table className="table dense-table">
            <thead>
              <tr>
                <th>Data</th>
                <th>Evento</th>
                <th>Pais</th>
                <th>Impacto</th>
                <th>Prev.</th>
                <th>Ant.</th>
              </tr>
            </thead>
            <tbody>
              {econ.length === 0 ? (
                <tr>
                  <td colSpan={6} className="muted">
                    Nenhum evento economico carregado ainda.
                  </td>
                </tr>
              ) : (
                econ.map((e, i) => (
                  <tr key={i}>
                    <td>{fmtDateTime(e.event_date)}</td>
                    <td>{e.event_name}</td>
                    <td>{e.country}</td>
                    <td className={e.impact === 'high' ? 'down' : ''}>{e.impact}</td>
                    <td>{e.forecast}</td>
                    <td>{e.previous}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <h2>Earnings da watchlist</h2>
        <div className="table-scroll compact-scroll">
          <table className="table dense-table">
            <thead>
              <tr>
                <th>Data</th>
                <th>Simbolo</th>
                <th>EPS estimado</th>
                <th>Receita estimada</th>
              </tr>
            </thead>
            <tbody>
              {earnings.length === 0 ? (
                <tr>
                  <td colSpan={4} className="muted">
                    Nenhum earnings carregado ainda.
                  </td>
                </tr>
              ) : (
                earnings.map((e, i) => (
                  <tr key={i}>
                    <td>{new Date(e.event_date).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })}</td>
                    <td>{e.symbol}</td>
                    <td>{e.eps_estimate ?? '-'}</td>
                    <td>{e.revenue_estimate !== null ? e.revenue_estimate.toLocaleString('pt-BR') : '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
