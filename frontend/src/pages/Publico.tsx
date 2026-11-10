import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import '../styles/research.css';
import { api } from '../api/client';
import type { SignalLog } from '../types';

function pct(v: number) {
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

export function Publico() {
  const [log, setLog] = useState<SignalLog | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    api
      .get<SignalLog>('/api/public/track-record', { skipAuth: true })
      .then(setLog)
      .catch(() => setFailed(true));
  }, []);

  const agg = log?.result.aggregate;

  return (
    <main className="research-scope research-standalone">
      <h1>Monitor de risco para ações</h1>
      <p className="muted">
        Mostramos o risco de cada ativo (tendência, volatilidade, tamanho de posição, stop e resultados
        trimestrais). Não prevemos preço e não recomendamos compra ou venda: nossos testes com 30 ações, 15
        ETFs e 12 anos de dados não encontraram nenhum sinal de entrada que supere comprar e segurar de forma
        confiável. O que se repetiu foi a redução de risco.
      </p>
      <p>
        <Link to="/login">Entrar</Link> · <Link to="/cadastro">Criar conta</Link>
      </p>

      <section>
        <h2>Registro público de sinais</h2>
        <p className="muted">
          Todo dia após o fechamento gravamos se cada ativo está em tendência de alta. O arquivo só cresce, e
          o resultado abaixo inclui custos e as vezes em que a regra perde para comprar e segurar.
        </p>
        {failed && <p className="muted">Não foi possível carregar o registro agora.</p>}
        {log && log.entries === 0 && <p className="muted">Ainda sem registros.</p>}
        {log && log.entries > 0 && (
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
                  <span className="muted block-text">poucos dias = pouca informação</span>
                </div>
              </div>
            ) : (
              <p className="muted">Os primeiros resultados aparecem após dois fechamentos registrados.</p>
            )}
          </>
        )}
      </section>

      <footer className="disclaimer">
        Informação educacional, não é recomendação de investimento. Resultados passados não garantem
        resultados futuros.
      </footer>
    </main>
  );
}
