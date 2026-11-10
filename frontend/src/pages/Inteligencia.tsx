import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../api/client';
import { useToast } from '../context/ToastContext';
import type {
  DecisionJournal,
  DataQualityOverview,
  IntelligenceScore,
  MovementExplanation,
  Playbook,
  SignalQuality,
  WeeklyBrief,
} from '../types';

function ScorePill({ score }: { score: number }) {
  const tone = score >= 70 ? 'good' : score < 45 ? 'danger' : 'warn';
  return <span className={`status-pill ${tone}`}>{score}</span>;
}

export function Inteligencia() {
  const toast = useToast();
  const [radar, setRadar] = useState<IntelligenceScore[]>([]);
  const [brief, setBrief] = useState<WeeklyBrief | null>(null);
  const [quality, setQuality] = useState<SignalQuality[]>([]);
  const [decisions, setDecisions] = useState<DecisionJournal[]>([]);
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [dataQuality, setDataQuality] = useState<DataQualityOverview | null>(null);
  const [symbol, setSymbol] = useState('AAPL');
  const [score, setScore] = useState<IntelligenceScore | null>(null);
  const [explanation, setExplanation] = useState<MovementExplanation | null>(null);

  async function load() {
    try {
      const [radarData, briefData, qualityData, decisionsData, playbooksData, dataQualityData] = await Promise.all([
        api.get<{ scores: IntelligenceScore[] }>('/api/intelligence/radar'),
        api.get<WeeklyBrief>('/api/intelligence/weekly-brief'),
        api.get<SignalQuality[]>('/api/intelligence/signal-quality'),
        api.get<DecisionJournal[]>('/api/intelligence/decisions'),
        api.get<Playbook[]>('/api/intelligence/playbooks'),
        api.get<DataQualityOverview>('/api/intelligence/data-quality'),
      ]);
      setRadar(radarData.scores);
      setBrief(briefData);
      setQuality(qualityData);
      setDecisions(decisionsData);
      setPlaybooks(playbooksData);
      setDataQuality(dataQualityData);
    } catch {
      toast('Erro ao carregar inteligência de mercado', 'error');
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function analyze(e: FormEvent) {
    e.preventDefault();
    const clean = symbol.trim().toUpperCase();
    try {
      const [scoreData, explanationData] = await Promise.all([
        api.get<IntelligenceScore>(`/api/intelligence/score/${clean}`),
        api.get<MovementExplanation>(`/api/intelligence/explain/${clean}`),
      ]);
      setScore(scoreData);
      setExplanation(explanationData);
    } catch {
      toast('Erro ao analisar ativo', 'error');
    }
  }

  async function addDecision(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      await api.post('/api/intelligence/decisions', {
        symbol: form.get('symbol'),
        thesis: form.get('thesis'),
        trigger: form.get('trigger'),
        invalidation: form.get('invalidation'),
        timeframe: form.get('timeframe'),
        risk_notes: form.get('risk_notes'),
      });
      e.currentTarget.reset();
      toast('Decisão registrada', 'success');
      load();
    } catch {
      toast('Erro ao registrar decisão', 'error');
    }
  }

  return (
    <div className="container dashboard-container">
      <div className="page-header">
        <div>
          <p className="eyebrow">Copiloto de inteligência</p>
          <h1>Inteligência de Mercado</h1>
          <p className="muted">Radar, explicação verificável, score, playbooks, qualidade de sinais e diário de decisão.</p>
        </div>
      </div>

      <section className="dashboard-grid">
        <div className="panel">
          <h2>Radar</h2>
          <div className="table-scroll compact-scroll">
            <table className="table dense-table">
              <thead><tr><th>Ativo</th><th>Score</th><th>Leitura</th></tr></thead>
              <tbody>
                {radar.length === 0 ? (
                  <tr><td colSpan={3} className="muted">Adicione ativos na watchlist para gerar radar.</td></tr>
                ) : (
                  radar.map((row) => (
                    <tr key={row.symbol}><td>{row.symbol}</td><td><ScorePill score={row.score} /></td><td>{row.label}</td></tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <h2>Analisar ativo</h2>
          <form onSubmit={analyze}>
            <input value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="AAPL" required />
            <button type="submit">Analisar</button>
          </form>
          {score && (
            <div className="quality-box">
              <strong>{score.symbol} · {score.label}</strong>
              <span><ScorePill score={score.score} /></span>
              {score.factors.map((factor) => (
                <span key={`${factor.name}-${factor.evidence}`} className="muted">{factor.name}: {factor.evidence}</span>
              ))}
            </div>
          )}
        </div>
      </section>

      {explanation && (
        <section className="dashboard-grid">
          <div className="panel">
            <h2>Fatos</h2>
            <ul className="decision-list">{explanation.facts.map((item) => <li key={item}>{item}</li>)}</ul>
          </div>
          <div className="panel">
            <h2>Eventos e hipóteses</h2>
            <ul className="decision-list">
              {explanation.related_events.map((item) => <li key={item}>{item}</li>)}
              {explanation.hypotheses.map((item) => <li key={item} className="muted">{item}</li>)}
            </ul>
          </div>
        </section>
      )}

      <section className="dashboard-grid">
        <div className="panel">
          <h2>Resumo semanal</h2>
          <ul className="decision-list">
            {!brief ? <li className="muted">Sem resumo ainda.</li> : brief.summary.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
        <div className="panel">
          <h2>Qualidade dos sinais</h2>
          <ul className="source-list">
            {quality.length === 0 ? (
              <li className="muted">Nenhum alerta disparado ainda.</li>
            ) : (
              quality.map((row) => (
                <li key={row.symbol}><strong>{row.symbol}: ruído {row.noise_score}</strong><span>{row.alerts} alerta(s), {row.assessment}</span></li>
              ))
            )}
          </ul>
        </div>
      </section>

      <section className="panel">
        <h2>Qualidade dos dados</h2>
        <div className="metric-mini-grid">
          <div><span>Alta confiança</span><strong>{dataQuality?.confidence_counts.HIGH ?? 0}</strong></div>
          <div><span>Atenção</span><strong>{dataQuality?.confidence_counts.MEDIUM ?? 0}</strong></div>
          <div><span>Baixa</span><strong>{dataQuality?.confidence_counts.LOW ?? 0}</strong></div>
        </div>
        <div className="table-scroll compact-scroll">
          <table className="table dense-table">
            <thead>
              <tr><th>Ativo</th><th>Confiança</th><th>Divergência</th><th>Fontes</th><th>Problemas</th></tr>
            </thead>
            <tbody>
              {!dataQuality || dataQuality.rows.length === 0 ? (
                <tr><td colSpan={5} className="muted">Adicione ativos para auditar as fontes.</td></tr>
              ) : (
                dataQuality.rows.map((row) => (
                  <tr key={row.symbol}>
                    <td>{row.symbol}</td>
                    <td><span className={`status-pill ${row.confidence === 'HIGH' ? 'good' : row.confidence === 'MEDIUM' ? 'warn' : 'danger'}`}>{row.confidence}</span></td>
                    <td>{row.max_divergence_pct.toFixed(2)}%</td>
                    <td>{row.providers.filter((provider) => provider.available).map((provider) => provider.provider).join(', ') || '-'}</td>
                    <td className="muted">{row.issues.join(' ') || 'Sem problemas detectados.'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="dashboard-grid">
        <div className="panel">
          <h2>Playbooks</h2>
          <ul className="source-list">
            {playbooks.map((p) => (
              <li key={p.id}><strong>{p.name}</strong><span>{p.description}</span><span>{p.rule_preset}</span></li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <h2>Diário de decisão</h2>
          <form className="stack-form" onSubmit={addDecision}>
            <input name="symbol" placeholder="AAPL" required />
            <input name="thesis" placeholder="Tese" required />
            <input name="trigger" placeholder="Gatilho" />
            <input name="invalidation" placeholder="Invalidação" />
            <input name="timeframe" placeholder="Prazo" />
            <input name="risk_notes" placeholder="Risco" />
            <button type="submit">Registrar</button>
          </form>
          <ul className="source-list">
            {decisions.map((d) => (
              <li key={d.id}><strong>{d.symbol} · {d.status}</strong><span>{d.thesis}</span><span>{d.invalidation}</span></li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}
