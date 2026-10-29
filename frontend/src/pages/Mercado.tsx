import { useEffect, useState } from 'react';
import { api, fetchBlob } from '../api/client';
import { useToast } from '../context/ToastContext';
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
  const toast = useToast();
  const [tick, setTick] = useState(0);
  const [busy, setBusy] = useState<'refresh' | 'pdf' | 'csv' | 'json' | null>(null);
  const { data: news, lastUpdated } = usePolling<NewsItem[]>('/api/news?limit=40', 60000, [tick]);
  const { data: globalNews, lastUpdated: globalLastUpdated } = usePolling<GlobalNewsItem[]>(
    '/api/global-news?limit=60',
    60000,
    [tick],
  );
  const [econ, setEcon] = useState<EconomicEvent[]>([]);
  const [earnings, setEarnings] = useState<EarningsEvent[]>([]);

  useEffect(() => {
    api.get<EconomicEvent[]>('/api/economic-events?days_ahead=14&limit=50').then(setEcon).catch(() => {});
    api.get<EarningsEvent[]>('/api/earnings-events?days_ahead=14&limit=50').then(setEarnings).catch(() => {});
  }, [tick]);

  async function handleRefresh() {
    setBusy('refresh');
    try {
      await api.post('/api/reports/refresh');
      setTick((t) => t + 1);
      toast('Dados atualizados.', 'success');
    } catch {
      toast('Erro ao atualizar os dados.', 'error');
    } finally {
      setBusy(null);
    }
  }

  async function handleExport(kind: 'pdf' | 'csv' | 'json') {
    setBusy(kind);
    try {
      const path = kind === 'pdf' ? '/api/reports/pdf' : `/api/reports/export.${kind}`;
      const blob = await fetchBlob(path);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `monitor-nasdaq-${new Date().toISOString().slice(0, 16).replace(/[:T]/g, '-')}.${kind}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast('Erro ao exportar.', 'error');
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <p className="eyebrow">Monitor macro</p>
          <h1>Painel de Mercado</h1>
          <p className="muted">
            Noticias globais, eventos economicos, earnings e manchetes por ativo em um so lugar.
          </p>
        </div>
        <div className="page-actions">
          <button className="btn-secondary" disabled={busy !== null} onClick={handleRefresh}>
            {busy === 'refresh' ? 'Atualizando...' : 'Atualizar agora'}
          </button>
          <button className="btn-secondary" disabled={busy !== null} onClick={() => handleExport('pdf')}>
            PDF
          </button>
          <button className="btn-secondary" disabled={busy !== null} onClick={() => handleExport('csv')}>
            CSV
          </button>
          <button className="btn-secondary" disabled={busy !== null} onClick={() => handleExport('json')}>
            JSON
          </button>
        </div>
      </div>

      <section>
        <h2>
          Noticias do mundo e macro{' '}
          {globalLastUpdated && <span className="muted">(atualizado {globalLastUpdated.toLocaleTimeString('pt-BR')})</span>}
        </h2>
        <ul className="alert-list">
          {!globalNews || globalNews.length === 0 ? (
            <li className="muted">Nenhuma noticia global coletada ainda.</li>
          ) : (
            globalNews.map((n, i) => (
              <li key={i} className="market-news-row">
                <span className={`impact-pill ${n.impact_score >= 40 ? 'danger' : n.impact_score >= 20 ? 'warn' : ''}`}>
                  {n.impact_score}
                </span>
                <div>
                  <span className="muted">{fmtDateTime(n.published_at)}</span> -{' '}
                  <a href={n.url} target="_blank" rel="noopener noreferrer">
                    {n.headline}
                  </a>{' '}
                  {n.source && <span className="muted">({n.source})</span>}
                  <span className="muted block-text">categoria: {n.category}</span>
                </div>
              </li>
            ))
          )}
        </ul>
      </section>

      <section>
        <h2>
          Noticias por ativo{' '}
          {lastUpdated && <span className="muted">(atualizado {lastUpdated.toLocaleTimeString('pt-BR')})</span>}
        </h2>
        <ul className="alert-list">
          {!news || news.length === 0 ? (
            <li className="muted">Nenhuma noticia coletada ainda.</li>
          ) : (
            news.map((n, i) => (
              <li key={i}>
                <span className="muted">{fmtDateTime(n.published_at)}</span> - <strong>{n.symbol}</strong>{' '}
                <a href={n.url} target="_blank" rel="noopener noreferrer">
                  {n.headline}
                </a>{' '}
                {n.source && <span className="muted">({n.source})</span>}
              </li>
            ))
          )}
        </ul>
      </section>

      <section>
        <h2>Calendario economico (proximos dias)</h2>
        <div className="table-scroll">
          <table className="table">
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

      <section>
        <h2>Earnings da watchlist</h2>
        <div className="table-scroll">
          <table className="table">
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
