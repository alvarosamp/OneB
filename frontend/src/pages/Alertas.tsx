import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { RULE_META } from '../hooks/useRuleConditions';
import type { AlertLog, WatchlistItem } from '../types';

function fmtTime(iso: string) {
  return new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) + ' UTC';
}

export function Alertas() {
  const [symbols, setSymbols] = useState<string[]>([]);
  const [alerts, setAlerts] = useState<AlertLog[]>([]);
  const [symbolFilter, setSymbolFilter] = useState('');
  const [ruleTypeFilter, setRuleTypeFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<WatchlistItem[]>('/api/watchlist')
      .then((items) => setSymbols(items.map((i) => i.symbol).sort()))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Não foi possível carregar a watchlist.'));
  }, []);

  async function loadAlerts() {
    setLoading(true);
    const params = new URLSearchParams({ limit: '100' });
    if (symbolFilter) params.set('symbol', symbolFilter);
    if (ruleTypeFilter) params.set('rule_type', ruleTypeFilter);
    try {
      setAlerts(await api.get<AlertLog[]>(`/api/alerts?${params.toString()}`));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível carregar os alertas.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAlerts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbolFilter, ruleTypeFilter]);

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <p className="eyebrow">Sinais disparados</p>
          <h1>Alertas</h1>
          <p className="muted">Histórico de alertas gerados pelas suas regras de watchlist.</p>
        </div>
      </div>

      <section className="panel">
        <div className="panel-title">
          <h2>Filtrar</h2>
          <button type="button" className="link-btn" onClick={() => void loadAlerts()} disabled={loading}>
            Atualizar
          </button>
        </div>
        <div className="filters" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <select value={symbolFilter} onChange={(e) => setSymbolFilter(e.target.value)}>
            <option value="">Todos os símbolos</option>
            {symbols.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <select value={ruleTypeFilter} onChange={(e) => setRuleTypeFilter(e.target.value)}>
            <option value="">Todos os tipos</option>
            {Object.keys(RULE_META).map((rt) => (
              <option key={rt} value={rt}>
                {rt}
              </option>
            ))}
          </select>
        </div>

        {error && <p className="data-warning" role="status">{error}</p>}

        <ul className="compact-list">
          {loading ? (
            <li className="muted">Carregando...</li>
          ) : alerts.length === 0 ? (
            <li className="muted">Nenhum alerta encontrado com esse filtro.</li>
          ) : (
            alerts.map((a) => (
              <li key={a.id}>
                <span className="mini-symbol">{a.symbol}</span>
                <div>
                  <strong>{a.message}</strong>
                  <span>
                    {fmtTime(a.triggered_at)} · [{a.rule_type}]
                    {a.delivered_telegram ? ' · Telegram enviado' : ''}
                  </span>
                </div>
              </li>
            ))
          )}
        </ul>
      </section>

      <p className="disclaimer">
        Alertas são sinais técnicos calculados a partir das suas regras. Apenas informativo — não constitui recomendação de investimento.
      </p>
    </div>
  );
}
