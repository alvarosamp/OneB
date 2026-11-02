import { useEffect, useState } from 'react';
import { RiskPanelCard } from '../../components/RiskPanelCard';
import { api } from '../../api/client';
import type { SignalLog } from '../../types';

const SYMBOL_RE = /^[A-Z0-9^=.-]{1,16}$/;

function pct(v: number) {
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

export function Risco() {
  const [input, setInput] = useState('AAPL');
  const [symbol, setSymbol] = useState('AAPL');
  const [log, setLog] = useState<SignalLog | null>(null);

  useEffect(() => {
    api.get<SignalLog>('/api/research/signals').then(setLog).catch(() => setLog(null));
  }, []);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const s = input.trim().toUpperCase();
    if (SYMBOL_RE.test(s)) setSymbol(s);
  };

  const agg = log?.result.aggregate;

  return (
    <div className="page">
      <h1>Análise de risco</h1>
      <p className="muted">
        Regime, volatilidade, tamanho de posição, stop e eventos do ativo. Informa o risco; não prevê o preço
        nem recomenda compra ou venda.
      </p>

      <form onSubmit={submit} className="panel" style={{ display: 'flex', gap: 8 }}>
        <input
          aria-label="Ticker"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ex.: AAPL, NVDA, QQQ"
        />
        <button type="submit">Analisar</button>
      </form>

      <RiskPanelCard key={symbol} symbol={symbol} />

      <section>
        <h2>Registro de sinais em tempo real</h2>
        <p className="muted">
          Todo dia após o fechamento gravamos se cada ativo está em tendência de alta. O arquivo só cresce:
          nada é reescrito depois. Aqui está o resultado dessa regra contra comprar e segurar, com custos,
          incluindo as vezes em que ela perde.
        </p>
        {!log || log.entries === 0 ? (
          <p className="muted">Ainda sem registros. O primeiro entra no próximo fechamento do mercado.</p>
        ) : (
          <>
            <p className="muted">
              Desde {log.started} · {log.entries} registros
            </p>
            {agg ? (
              <div className="metric-grid">
                <div className="metric-card">
                  <span className="metric-label">Regra de tendência</span>
                  <strong className={agg.strategy_pct >= 0 ? 'up' : 'down'}>{pct(agg.strategy_pct)}</strong>
                  <span className="muted block-text">pior dia {pct(agg.worst_day_strategy_pct)}</span>
                </div>
                <div className="metric-card">
                  <span className="metric-label">Comprar e segurar</span>
                  <strong className={agg.buy_hold_pct >= 0 ? 'up' : 'down'}>{pct(agg.buy_hold_pct)}</strong>
                  <span className="muted block-text">pior dia {pct(agg.worst_day_buy_hold_pct)}</span>
                </div>
                <div className="metric-card">
                  <span className="metric-label">Dias medidos</span>
                  <strong>{agg.days}</strong>
                  <span className="muted block-text">pouco tempo = pouca informação</span>
                </div>
              </div>
            ) : (
              <p className="muted">Os primeiros resultados aparecem quando houver ao menos dois fechamentos registrados.</p>
            )}
            <div className="table-scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th>Data</th>
                    <th>Ativo</th>
                    <th>Estado</th>
                    <th>Fechamento</th>
                  </tr>
                </thead>
                <tbody>
                  {log.recent.map((r) => (
                    <tr key={`${r.date}-${r.symbol}`}>
                      <td>{r.date}</td>
                      <td>{r.symbol}</td>
                      <td>{r.state ? 'Em tendência de alta' : 'Fora'}</td>
                      <td>{r.close.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
