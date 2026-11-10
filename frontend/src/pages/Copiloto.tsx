import { useState, type FormEvent } from 'react';
import { api } from '../api/client';
import type { CopilotAnalysis } from '../types';

function biasLabel(bias: string) {
  if (bias === 'OBSERVAR_COMPRA') return 'Observar compra';
  if (bias === 'EVITAR_POR_ENQUANTO') return 'Evitar por enquanto';
  return 'Aguardar confirmacao';
}

const METRIC_LABELS: Record<string, string> = {
  retorno_periodo_pct: 'Retorno no período',
  drawdown_max_pct: 'Queda máxima',
  sharpe_aprox: 'Sharpe (aprox.)',
  sortino_aprox: 'Sortino (aprox.)',
  taxa_acerto_dias_pct: 'Dias positivos',
  expectativa_diaria_pct: 'Expectativa diária',
};

const METRIC_IS_PERCENT = new Set([
  'retorno_periodo_pct',
  'drawdown_max_pct',
  'taxa_acerto_dias_pct',
  'expectativa_diaria_pct',
]);

function metricLabel(key: string) {
  return METRIC_LABELS[key] ?? key.replaceAll('_', ' ');
}

function metricValue(key: string, value: number) {
  return METRIC_IS_PERCENT.has(key) ? `${value.toFixed(2)}%` : value.toFixed(2);
}

export function Copiloto() {
  const [symbol, setSymbol] = useState('NVDA');
  const [capital, setCapital] = useState('20000');
  const [riskPct, setRiskPct] = useState('1');
  const [question, setQuestion] = useState('Quero operar hoje. Vale a pena olhar esse ativo?');
  const [analysis, setAnalysis] = useState<CopilotAnalysis | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const result = await api.post<CopilotAnalysis>('/api/copilot/analyze', {
        symbol,
        question,
        capital_usd: Number(capital),
        risk_budget_pct: Number(riskPct),
      });
      setAnalysis(result);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container dashboard-container">
      <div className="page-header">
        <div>
          <p className="eyebrow">Copiloto de trading</p>
          <h1>Decisao explicavel</h1>
          <p className="muted">
            Multiagentes analisam tecnico, noticias, macro, risco e perfil. Sem broker e sem ordem automatica.
          </p>
        </div>
      </div>

      <section className="panel">
        <form className="copilot-form" onSubmit={handleSubmit}>
          <label className="field-label">
            Ativo
            <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} required />
          </label>
          <label className="field-label">
            Capital US$
            <input type="number" min="0" step="1" value={capital} onChange={(e) => setCapital(e.target.value)} />
          </label>
          <label className="field-label">
            Risco max. %
            <input type="number" min="0.1" max="10" step="0.1" value={riskPct} onChange={(e) => setRiskPct(e.target.value)} />
          </label>
          <label className="field-label copilot-question">
            Pergunta
            <textarea value={question} rows={3} onChange={(e) => setQuestion(e.target.value)} />
          </label>
          <button type="submit" disabled={loading}>
            {loading ? 'Analisando...' : 'Analisar'}
          </button>
        </form>
      </section>

      {analysis && (
        <>
          <section className="metric-grid">
            <div className="metric-card">
              <span className="metric-label">Decisao final</span>
              <strong>{biasLabel(analysis.bias)}</strong>
              <span className="muted">{analysis.symbol} a {analysis.entry_price ?? '-'} USD</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Confianca</span>
              <strong>{analysis.confidence}%</strong>
              <span className="muted">media dos agentes</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Votos comprar</span>
              <strong>{analysis.votes.filter((v) => v.vote === 'Comprar').length}</strong>
              <span className="muted">de {analysis.votes.length} agentes</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Risco</span>
              <strong>{riskPct}%</strong>
              <span className="muted">limite definido por voce</span>
            </div>
          </section>

          <section className="panel trade-plan">
            <div className="panel-title">
              <div>
                <h2>Plano técnico condicional</h2>
                <p className="muted">Ações Nasdaq/EUA · base diária · sem execução automática</p>
              </div>
              {analysis.trade_plan.available && <span className="status-pill warn">{analysis.trade_plan.status}</span>}
            </div>
            {!analysis.trade_plan.available ? (
              <p className="muted">{analysis.trade_plan.reason}</p>
            ) : (
              <>
                <div className="metric-mini-grid trade-plan-grid">
                  <div><span>Entrada de referência</span><strong>US$ {analysis.trade_plan.entry_price?.toFixed(2)}</strong></div>
                  <div><span>Invalidação / stop</span><strong>US$ {analysis.trade_plan.stop_price?.toFixed(2)}</strong></div>
                  <div><span>Alvo 1 (2R)</span><strong>US$ {analysis.trade_plan.target_1_price?.toFixed(2)}</strong></div>
                  <div><span>Alvo 2 (3R)</span><strong>US$ {analysis.trade_plan.target_2_price?.toFixed(2)}</strong></div>
                  <div><span>Tamanho máximo</span><strong>{analysis.trade_plan.suggested_shares} ação(ões)</strong></div>
                  <div><span>Risco planejado</span><strong>US$ {analysis.trade_plan.risk_amount_usd?.toFixed(2)}</strong></div>
                </div>
                <ul className="decision-list">
                  <li>{analysis.trade_plan.reason}</li>
                  <li>{analysis.trade_plan.invalidation}</li>
                  <li>Suporte de 20 dias: US$ {analysis.trade_plan.support_20d?.toFixed(2)} · Resistência de 20 dias: US$ {analysis.trade_plan.resistance_20d?.toFixed(2)}.</li>
                  <li>Janela de acompanhamento: {analysis.trade_plan.holding_window}; plano calculado no timeframe {analysis.trade_plan.timeframe}.</li>
                </ul>
              </>
            )}
          </section>

          <section className="dashboard-grid">
            <div className="panel panel-wide">
              <h2>Estamos olhando porque...</h2>
              <ul className="decision-list">
                {analysis.why.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="panel">
              <h2>Tese contraria</h2>
              <ul className="compact-list">
                {analysis.contrary_view.length === 0 ? (
                  <li className="muted">Nenhum contraponto forte detectado.</li>
                ) : (
                  analysis.contrary_view.map((item) => (
                    <li key={item}>{item}</li>
                  ))
                )}
              </ul>
            </div>
          </section>

          <section className="panel">
            <h2>Como cada especialista votou</h2>
            <div className="agents-grid">
              {analysis.votes.map((vote) => (
                <article className="agent-card" key={vote.name}>
                  <div className="panel-title">
                    <h3>{vote.name}</h3>
                    <span className={`status-pill ${vote.vote === 'Comprar' ? 'good' : vote.vote === 'Evitar' ? 'danger' : 'warn'}`}>
                      {vote.vote} · {vote.confidence}%
                    </span>
                  </div>
                  <p className="muted">{vote.summary}</p>
                  {vote.evidence.length > 0 && (
                    <details className="agent-evidence">
                      <summary>Ver detalhes técnicos</summary>
                      <ul className="decision-list">
                        {vote.evidence.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                </article>
              ))}
            </div>
          </section>

          <section className="dashboard-grid">
            <div className="panel">
              <h2>Plano de risco</h2>
              <ul className="decision-list">
                {analysis.risk_plan.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="panel">
              <h2>Simulador rapido</h2>
              <p className="muted">{analysis.simulation.summary}</p>
              <div className="metric-mini-grid">
                {Object.entries(analysis.simulation.metrics).map(([key, value]) => (
                  <div key={key}>
                    <span>{metricLabel(key)}</span>
                    <strong>{metricValue(key, value)}</strong>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="panel">
            <h2>Padroes detectados na watchlist</h2>
            <ul className="decision-list">
              {analysis.patterns.length === 0 ? (
                <li className="muted">Nenhum padrao forte encontrado agora.</li>
              ) : (
                analysis.patterns.map((item) => <li key={item}>{item}</li>)
              )}
            </ul>
            <p className="muted">{analysis.disclaimer}</p>
          </section>
        </>
      )}
    </div>
  );
}
