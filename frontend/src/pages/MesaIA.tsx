import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import type { DecisionDesk, MarketDivergence, RecommendationDecision, ReliabilityScoreboard } from '../types';
import { useToast } from '../context/ToastContext';
import { ReliabilityChart } from '../components/ReliabilityChart';

function actionLabel(action: string) {
  if (action === 'BUY_CONTROLLED') return 'Compra controlada';
  if (action === 'WATCH_BUY') return 'Observar compra';
  if (action === 'SELL_SHORT') return 'Venda a descoberto';
  if (action === 'WATCH_SHORT') return 'Observar venda';
  if (action === 'AVOID') return 'Evitar';
  return 'Esperar';
}

function actionClass(action: string) {
  if (action === 'BUY_CONTROLLED') return 'good';
  if (action === 'WATCH_BUY') return 'warn';
  if (action === 'SELL_SHORT') return 'short';
  if (action === 'WATCH_SHORT') return 'warn-short';
  if (action === 'AVOID') return 'danger';
  return 'neutral';
}

function pct(value: number | null | undefined) {
  return value === null || value === undefined ? '-' : `${value.toFixed(2)}%`;
}

function confidenceBand(value: number | null | undefined) {
  if (value === null || value === undefined) return { cls: 'low', label: 'Sem dado' };
  if (value >= 70) return { cls: 'high', label: 'Alta' };
  if (value >= 45) return { cls: 'mid', label: 'Média' };
  return { cls: 'low', label: 'Baixa' };
}

function ConfidenceBadge({ value }: { value: number | null | undefined }) {
  const { cls, label } = confidenceBand(value);
  return (
    <span className={`confidence ${cls}`}>
      <i />
      {label}
      {value !== null && value !== undefined ? ` · ${value}%` : ''}
    </span>
  );
}

export function MesaIA() {
  const toast = useToast();
  const [desk, setDesk] = useState<DecisionDesk | null>(null);
  const [history, setHistory] = useState<RecommendationDecision[]>([]);
  const [scoreboard, setScoreboard] = useState<ReliabilityScoreboard | null>(null);
  const [divergence, setDivergence] = useState<MarketDivergence | null>(null);
  const [loading, setLoading] = useState(true);
  const [recording, setRecording] = useState(false);

  const load = useCallback(async (record = false) => {
    if (record) {
      setRecording(true);
    } else {
      setLoading(true);
    }
    try {
      const [deskData, historyData, scoreboardData, divergenceData] = await Promise.all([
        api.get<DecisionDesk>(`/api/decision-desk/recommendations${record ? '?record=true' : ''}`),
        api.get<RecommendationDecision[]>('/api/decision-desk/history?limit=20'),
        api.get<ReliabilityScoreboard>('/api/decision-desk/scoreboard'),
        api.get<MarketDivergence>('/api/decision-desk/market-divergence'),
      ]);
      setDesk(deskData);
      setHistory(historyData);
      setScoreboard(scoreboardData);
      setDivergence(divergenceData);
      if (record) toast(`${deskData.recorded} recomendações registradas na memória`, 'success');
    } catch {
      toast('Erro ao carregar a Mesa IA', 'error');
    } finally {
      setLoading(false);
      setRecording(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const recommendations = desk?.recommendations ?? [];
  const buyRows = recommendations.filter((row) => row.action === 'BUY_CONTROLLED');
  const watchRows = recommendations.filter((row) => row.action === 'WATCH_BUY');
  const shortRows = recommendations.filter((row) => row.action === 'SELL_SHORT');
  const watchShortRows = recommendations.filter((row) => row.action === 'WATCH_SHORT');

  return (
    <div className="container decision-desk">
      <section className="page-header">
        <div>
          <p className="eyebrow">Copiloto Temporal de Mercado</p>
          <h1>Mesa IA</h1>
          <p>Recomendações auditáveis com motivo, score, memória de falso positivo e plano de risco.</p>
          <p className="muted">Motor de regras e risco decide; o LLM apenas explica. Pesquisa experimental fica na Mesa Técnica.</p>
        </div>
        <button type="button" onClick={() => load(true)} disabled={recording || loading}>
          {recording ? 'Registrando...' : 'Registrar leitura'}
        </button>
      </section>

      {loading && <p className="muted">Calculando recomendações...</p>}

      {desk?.circuit_breaker.tripped && (
        <div className="circuit-breaker-banner">
          ⚠️ Freio de portfólio ativo: taxa de acerto recente de {desk.circuit_breaker.win_rate_pct}% em{' '}
          {desk.circuit_breaker.samples} recomendações. Compras rebaixadas para observação até o placar melhorar.
        </div>
      )}

      {desk?.decision_health.tripped && (
        <div className="circuit-breaker-banner">
          ℹ️ Mesa em modo {desk.decision_health.operating_mode}: {desk.decision_health.reason} Sinais seguem visíveis apenas para observação.
        </div>
      )}

      {divergence?.available && (
        <div className={`divergence-banner${divergence.divergent ? ' divergent' : ''}`}>
          {divergence.divergent ? '⚠️' : 'ℹ️'} {divergence.note}
          <span className="divergence-numbers">
            Convicção líquida da IA: {divergence.ai_lean_yesterday} → {divergence.ai_lean_today} · {divergence.benchmark_symbol}:{' '}
            {divergence.benchmark_move_pct}%
          </span>
        </div>
      )}

      {desk && (
        <>
          <section className="decision-summary">
            <div>
              <span>Agora</span>
              <strong>{desk.headline}</strong>
            </div>
            <div>
              <span>Benchmark</span>
              <strong>{desk.benchmark}</strong>
            </div>
            <div>
              <span>Calibração</span>
              <strong>{desk.calibration_source === 'walk_forward_calibrated' ? 'Walk-forward validada' : 'Padrão estático'}</strong>
            </div>
            <div>
              <span>Compras</span>
              <strong>{buyRows.length}</strong>
            </div>
            <div>
              <span>Observação (compra)</span>
              <strong>{watchRows.length}</strong>
            </div>
            <div>
              <span>Vendas</span>
              <strong>{shortRows.length}</strong>
            </div>
            <div>
              <span>Observação (venda)</span>
              <strong>{watchShortRows.length}</strong>
            </div>
            {desk.macro_context.dxy !== null && (
              <div>
                <span>DXY</span>
                <strong>
                  {desk.macro_context.dxy} ({desk.macro_context.dxy_change_20d_pct! >= 0 ? '+' : ''}
                  {desk.macro_context.dxy_change_20d_pct}% 20d)
                </strong>
              </div>
            )}
            {desk.macro_context.oil !== null && (
              <div>
                <span>Petróleo (WTI)</span>
                <strong>
                  ${desk.macro_context.oil} ({desk.macro_context.oil_change_20d_pct! >= 0 ? '+' : ''}
                  {desk.macro_context.oil_change_20d_pct}% 20d)
                </strong>
              </div>
            )}
          </section>

          <section className="decision-grid">
            {recommendations.map((row) => (
              <article key={row.symbol} className={`decision-card ${actionClass(row.action)}`}>
                <header>
                  <div>
                    <strong>{row.symbol}</strong>
                    <span>{actionLabel(row.action)}</span>
                  </div>
                  <ConfidenceBadge value={row.confidence} />
                </header>
                <div className="decision-metrics">
                  <span>Preço <b>${row.price.toFixed(2)}</b></span>
                  <span>Score <b>{row.score}</b></span>
                  <span>Tamanho <b>{row.suggested_size_pct}%</b></span>
                  {row.probability_win_pct !== null && (
                    <span>P({row.direction === 'short' ? 'queda' : 'ganho'}) <b>{row.probability_win_pct}%</b></span>
                  )}
                </div>
                <p>{row.fair_reason}</p>
                {row.ai_narrative && <p className="ai-narrative">🤖 {row.ai_narrative}</p>}
                <ul>
                  {row.evidence.slice(0, 3).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
                <footer>
                  <span>Stop {row.stop_price ? `$${row.stop_price.toFixed(2)}` : '-'}</span>
                  <span>Alvo {row.target_price ? `$${row.target_price.toFixed(2)}` : '-'}</span>
                </footer>
              </article>
            ))}
          </section>

          <section className="decision-history">
            <h2>Placar de Confiabilidade</h2>
            <p>Compara a confiança que a IA declarou com o acerto real, checado 5 pregões depois.</p>
            {scoreboard && <ReliabilityChart data={scoreboard} />}
          </section>

          <section className="decision-history">
            <h2>Memória Temporal</h2>
            <table>
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Ativo</th>
                  <th>Ação</th>
                  <th>Confiança</th>
              <th>Resultado</th>
              <th>1d</th>
              <th>Retorno 5d</th>
              <th>20d</th>
              <th>Regime / modelo</th>
                </tr>
              </thead>
              <tbody>
                {history.map((row) => (
                  <tr key={row.id}>
                    <td>{new Date(row.created_at).toLocaleDateString()}</td>
                    <td>{row.symbol}</td>
                    <td>{actionLabel(row.action)}</td>
                    <td><ConfidenceBadge value={row.confidence} /></td>
                    <td>{row.outcome_status}</td>
                    <td>{pct(row.outcome_return_1d_pct)}</td>
                    <td>{pct(row.outcome_return_5d_pct)}</td>
                    <td>{pct(row.outcome_return_20d_pct)}</td>
                    <td>{row.regime} · {row.model_id}@{row.model_version}</td>
                  </tr>
                ))}
                {!history.length && (
                  <tr>
                    <td colSpan={9} className="muted">Registre uma leitura para iniciar a memória temporal.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}
