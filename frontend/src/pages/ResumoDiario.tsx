import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { DailyMarketAsset, DailyMarketSummary } from '../types';

function fmtMoney(value: number | null) {
  if (value === null) return '-';
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'USD' });
}

function fmtPct(value: number | null, signed = false) {
  if (value === null) return '-';
  const prefix = signed && value > 0 ? '+' : '';
  return `${prefix}${value.toFixed(2)}%`;
}

function fmtDateTime(iso: string) {
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function scoreTone(score: number) {
  if (score >= 65) return 'good';
  if (score <= 45) return 'danger';
  return 'warn';
}

function AssetTable({ rows, empty }: { rows: DailyMarketAsset[]; empty: string }) {
  return (
    <div className="table-scroll compact-scroll">
      <table className="table dense-table">
        <thead>
          <tr>
            <th>Ativo</th>
            <th>Score</th>
            <th>Preco</th>
            <th>Dia</th>
            <th>Tendencia</th>
            <th>Vol.</th>
            <th>RSI</th>
            <th>Notas</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={8} className="muted">
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={row.symbol}>
                <td>
                  <strong>{row.symbol}</strong>
                  {row.label && <span className="muted block-text">{row.label}</span>}
                </td>
                <td>
                  <span className={`status-pill ${scoreTone(row.score)}`}>{row.score}</span>
                </td>
                <td>{fmtMoney(row.price)}</td>
                <td className={(row.change_pct ?? 0) >= 0 ? 'up' : 'down'}>{fmtPct(row.change_pct, true)}</td>
                <td>{row.trend}</td>
                <td>
                  {row.volatility_label}
                  <span className="muted block-text">ATR {fmtPct(row.atr_pct)}</span>
                </td>
                <td>{row.rsi?.toFixed(1) ?? '-'}</td>
                <td className="muted">{row.notes.join(' ') || '-'}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export function ResumoDiario() {
  const [summary, setSummary] = useState<DailyMarketSummary | null>(null);
  const [status, setStatus] = useState('Carregando resumo diario...');

  async function load() {
    try {
      const data = await api.get<DailyMarketSummary>('/api/reports/daily-summary');
      setSummary(data);
      setStatus(`Atualizado ${fmtDateTime(data.generated_at)}`);
    } catch {
      setStatus('Erro ao carregar resumo diario.');
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="container dashboard-container">
      <div className="page-header">
        <div>
          <p className="eyebrow">Relatorio diario</p>
          <h1>Resumo do Mercado</h1>
          <p className="muted">{status}</p>
        </div>
        <button type="button" className="btn-link" onClick={load}>
          Atualizar
        </button>
      </div>

      {!summary ? (
        <section className="panel">
          <p>{status}</p>
        </section>
      ) : (
        <>
          <section className="daily-hero panel">
            <div>
              <span className="metric-label">Tom do mercado</span>
              <strong>{summary.market_tone}</strong>
            </div>
            <p>{summary.headline}</p>
          </section>

          <section className="dashboard-grid">
            <div className="panel">
              <h2>Principais leituras</h2>
              <ul className="decision-list">
                {summary.key_takeaways.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="panel">
              <h2>Plano do dia</h2>
              <ul className="decision-list">
                {summary.action_plan.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </section>

          <section className="panel">
            <h2>Oportunidades tecnicas</h2>
            <AssetTable rows={summary.opportunities} empty="Nenhum ativo com score alto e leitura limpa agora." />
          </section>

          <section className="panel">
            <h2>Riscos e volatilidade</h2>
            <AssetTable rows={summary.risks} empty="Nenhum risco relevante detectado na watchlist." />
          </section>

          <section className="panel">
            <h2>Observar</h2>
            <AssetTable rows={summary.watch} empty="Nada na zona intermediaria por enquanto." />
          </section>

          <section className="dashboard-grid">
            <div className="panel">
              <h2>Eventos macro</h2>
              <ul className="source-list">
                {summary.macro_events.length === 0 ? (
                  <li className="muted">Nenhum evento economico carregado.</li>
                ) : (
                  summary.macro_events.map((event) => (
                    <li key={`${event.date}-${event.name}`}>
                      <strong>
                        {fmtDateTime(event.date)} · {event.name}
                      </strong>
                      <span>
                        {event.country} · impacto {event.impact} · prev. {event.forecast || '-'} · ant.{' '}
                        {event.previous || '-'}
                      </span>
                    </li>
                  ))
                )}
              </ul>
            </div>
            <div className="panel">
              <h2>Noticias de maior impacto</h2>
              <ul className="source-list">
                {summary.top_news.length === 0 ? (
                  <li className="muted">Nenhuma noticia global carregada.</li>
                ) : (
                  summary.top_news.map((item) => (
                    <li key={item.url}>
                      <strong>
                        <a href={item.url} target="_blank" rel="noopener noreferrer">
                          {item.headline}
                        </a>
                      </strong>
                      <span>
                        impacto {item.impact_score} · {item.category} · {item.source || 'fonte nao informada'}
                      </span>
                    </li>
                  ))
                )}
              </ul>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
