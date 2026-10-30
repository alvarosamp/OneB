import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { RiskPanel } from '../types';

function pct(v: number | null | undefined, digits = 1) {
  return v === null || v === undefined ? '-' : `${v.toFixed(digits)}%`;
}

export function RiskPanelCard({ symbol }: { symbol: string }) {
  const [panel, setPanel] = useState<RiskPanel | null>(null);
  const [riskPct, setRiskPct] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    api
      .get<RiskPanel>(`/api/research/panel/${symbol}?risk_pct=${riskPct}`)
      .then((p) => !cancelled && setPanel(p))
      .catch(() => !cancelled && setError('Não foi possível montar o painel de risco deste ativo.'))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [symbol, riskPct]);

  if (error) return <p className="muted">{error}</p>;
  if (!panel) return <p className="muted">{loading ? 'Montando painel de risco...' : ''}</p>;

  const { regime, volatility, levels, sizing, earnings, news } = panel;

  return (
    <section>
      <h2>
        Painel de risco <span className="muted">(dados até {panel.as_of})</span>
      </h2>

      {panel.alerts.length > 0 && (
        <div className="panel">
          <ul>
            {panel.alerts.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="metric-grid">
        <div className="metric-card">
          <span className="metric-label">Tendência</span>
          <strong className={regime.trend === 'up' ? 'up' : regime.trend === 'down' ? 'down' : ''}>
            {regime.trend_label ?? 'n/d'}
          </strong>
          <span className="muted block-text">há {regime.trend_bars} barras</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Volatilidade</span>
          <strong>{regime.volatility_label ?? 'n/d'}</strong>
          <span className="muted block-text">
            {pct(volatility.realized_20d_pct, 0)} a.a. · ATR {pct(volatility.atr_pct, 2)}
          </span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Exposição relativa (vol-alvo {sizing.target_vol_pct}%)</span>
          <strong>{sizing.relative_exposure_pct}%</strong>
          <span className="muted block-text">100% = alocação cheia; menor = ativo mais volátil</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Distância das médias</span>
          <strong>
            SMA50 {pct(levels.dist_sma50_pct)} · SMA200 {pct(levels.dist_sma200_pct)}
          </strong>
          <span className="muted block-text">
            {pct(levels.drawdown_from_52w_high_pct)} da máxima de 52 semanas
          </span>
        </div>
      </div>

      <h3>Tamanho de posição por risco</h3>
      <div className="panel">
        <label className="field-label">
          Aceito perder (% do capital)
          <input
            type="number"
            min={0.1}
            max={10}
            step={0.1}
            value={riskPct}
            onChange={(e) => {
              const v = Number(e.target.value);
              if (v > 0 && v <= 10) setRiskPct(v);
            }}
          />
        </label>
        <p>
          Stop de {sizing.stop_atr_mult} ATR = {pct(sizing.stop_distance_pct, 2)} abaixo do preço. Com risco de{' '}
          {sizing.risk_pct}% do capital, a posição seria de{' '}
          <strong>{pct(sizing.position_pct_of_capital)} do capital</strong>. Stop móvel (máxima de 22 dias − 3
          ATR): <strong>{sizing.trailing_stop_price.toFixed(2)}</strong>
          {sizing.stop_breached && <span className="down"> — já rompido pelo preço atual</span>}.
        </p>
      </div>

      <h3>Resultado trimestral</h3>
      <div className="panel">
        {earnings.next_date ? (
          <p>
            Próximo: <strong>{earnings.next_date}</strong> (em {earnings.days_until} dia(s)).
          </p>
        ) : (
          <p className="muted">Data do próximo resultado indisponível.</p>
        )}
        {earnings.history ? (
          <p>
            Em {earnings.history.events} resultados passados o preço se mexeu em média{' '}
            <strong>±{pct(earnings.history.avg_abs_move_pct)}</strong> no dia (dia normal:{' '}
            {pct(earnings.history.typical_day_move_pct)}). Faixa típica {pct(earnings.history.p05_pct)} a{' '}
            {pct(earnings.history.p95_pct)}; pior {pct(earnings.history.worst_pct)}; subiu em{' '}
            {earnings.history.up_share_pct}% das vezes.
          </p>
        ) : (
          <p className="muted">Histórico de reações insuficiente.</p>
        )}
      </div>

      <h3>
        Notícias <span className="muted">({news.count_7d} em 7 dias · {news.count_30d} em 30 dias)</span>
      </h3>
      <div className="panel">
        {news.latest.length === 0 ? (
          <p className="muted">Nenhuma manchete arquivada para este ativo ainda.</p>
        ) : (
          <ul className="alert-list">
            {news.latest.map((n) => (
              <li key={`${n.published_at}-${n.headline}`}>
                <span className="muted">{new Date(n.published_at).toLocaleDateString('pt-BR')} · {n.source}</span>
                <br />
                {n.headline}
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="muted">{panel.evidence}</p>
    </section>
  );
}
