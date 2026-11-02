import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useToast } from '../context/ToastContext';
import type { ResearchEventRow, ResearchStudy } from '../types';

function heatColor(r: number | null) {
  if (r === null) return undefined;
  const alpha = Math.min(Math.abs(r), 1) * 0.75;
  return r >= 0 ? `rgba(34, 160, 90, ${alpha})` : `rgba(210, 70, 70, ${alpha})`;
}

function EventTable({ title, rows }: { title: string; rows: ResearchEventRow[] }) {
  return (
    <div>
      <strong>{title}</strong>
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th>Horizonte</th>
              <th>Eventos</th>
              <th>Média</th>
              <th>Acerto</th>
              <th>Excesso vs base</th>
              <th>t</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.horizon}>
                <td>{r.horizon}d</td>
                <td className={r.n < 10 ? 'muted' : ''}>{r.n}</td>
                <td>{r.mean_pct === null ? '-' : `${r.mean_pct}%`}</td>
                <td>{r.hit_rate === null ? '-' : `${Math.round(r.hit_rate * 100)}%`}</td>
                <td>{r.excess_pct === null ? '-' : `${r.excess_pct}%`}</td>
                <td className={r.t_stat !== null && Math.abs(r.t_stat) >= 2 ? '' : 'muted'}>
                  {r.t_stat ?? '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function Pesquisa() {
  const [study, setStudy] = useState<ResearchStudy | null>(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const toast = useToast();

  async function run(refresh: boolean) {
    setLoading(true);
    try {
      const qs = new URLSearchParams({ refresh: String(refresh) });
      if (input.trim()) qs.set('symbols', input.trim());
      setStudy(await api.get<ResearchStudy>(`/api/research/study?${qs}`));
    } catch {
      toast('Erro ao rodar o estudo. Verifique os símbolos.', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    run(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const symbols = study?.symbols ?? [];

  return (
    <div className="container dashboard-container">
      <div className="page-header">
        <div>
          <p className="eyebrow">Pesquisa</p>
          <h1>Tendências e correlações</h1>
          <p className="muted">
            Calculado a partir do histórico diário salvo localmente. Sem símbolos, usa sua watchlist
            mais QQQ, SPY e ouro. &quot;Atualizar dados&quot; baixa histórico novo (mais lento).
          </p>
        </div>
      </div>

      <div className="panel">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ex: NVDA, AAPL, GC=F (vazio = watchlist)"
          aria-label="Símbolos"
        />{' '}
        <button type="button" onClick={() => run(false)} disabled={loading}>
          Analisar
        </button>{' '}
        <button type="button" onClick={() => run(true)} disabled={loading}>
          {loading ? 'Carregando...' : 'Atualizar dados e analisar'}
        </button>
      </div>

      {!study ? (
        <p className="muted">Carregando...</p>
      ) : study.error ? (
        <p className="muted">
          {study.error} Clique em &quot;Atualizar dados e analisar&quot; para baixar o histórico.
        </p>
      ) : (
        <>
          <p className="muted">
            Período {study.period?.[0]} a {study.period?.[1]} · {study.pairs_tested} pares testados ·{' '}
            {study.pairs_significant} significativos após correção de múltiplos testes
          </p>

          <section>
            <h2>Mapa de correlação (retornos diários)</h2>
            <div className="table-scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th />
                    {symbols.map((s) => (
                      <th key={s}>{s}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {symbols.map((row, i) => (
                    <tr key={row}>
                      <th>{row}</th>
                      {symbols.map((col, j) => {
                        const r = study.matrix?.[i]?.[j] ?? null;
                        return (
                          <td key={col} style={{ background: heatColor(r), textAlign: 'center' }}>
                            {r === null ? '-' : r.toFixed(2)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2>Maiores correlações</h2>
            <div className="table-scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th>Par</th>
                    <th>r</th>
                    <th>Amostra</th>
                    <th>p ajustado</th>
                    <th>Significativa</th>
                  </tr>
                </thead>
                <tbody>
                  {study.top_correlations?.map((p) => (
                    <tr key={`${p.a}-${p.b}`}>
                      <td>
                        {p.a} × {p.b}
                      </td>
                      <td>{p.r.toFixed(2)}</td>
                      <td>{p.n}</td>
                      <td>{p.p_adj === null ? '-' : p.p_adj.toFixed(4)}</td>
                      <td>{p.significant ? 'sim' : 'não'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2>Relações que mudaram (últimos 60 dias vs. período todo)</h2>
            <div className="table-scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th>Par</th>
                    <th>r total</th>
                    <th>r recente</th>
                    <th>Variação</th>
                  </tr>
                </thead>
                <tbody>
                  {study.biggest_drifts?.slice(0, 8).map((d) => (
                    <tr key={`${d.a}-${d.b}`}>
                      <td>
                        {d.a} × {d.b}
                      </td>
                      <td>{d.r_full.toFixed(2)}</td>
                      <td>{d.r_recent.toFixed(2)}</td>
                      <td className={d.delta >= 0 ? 'up' : 'down'}>{d.delta.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2>Regime e eventos por ativo</h2>
            {symbols.map((s) => {
              const info = study.per_symbol?.[s];
              if (!info) return null;
              return (
                <details key={s} className="panel">
                  <summary>
                    <strong>{s}</strong> · tendência {info.regime.trend_label ?? 'n/d'} (
                    {info.regime.trend_bars} barras) · volatilidade{' '}
                    {info.regime.volatility_label ?? 'n/d'} · {info.bars} barras de histórico
                  </summary>
                  <EventTable title="Após RSI cruzar abaixo de 30" rows={info.rsi_below_30} />
                  <EventTable title="Após golden cross (média 50 > 200)" rows={info.golden_cross} />
                </details>
              );
            })}
          </section>

          <section>
            <h2>Cuidados ao interpretar</h2>
            <ul>
              {study.caveats?.map((c) => (
                <li key={c} className="muted">
                  {c}
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
