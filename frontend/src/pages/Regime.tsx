import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../api/client';
import { usePolling } from '../hooks/usePolling';

interface RegimeFactor {
  name: string;
  impact: number | null;
  evidence: string;
}

interface LocalRegime {
  label: string;
  score: number;
  factors: RegimeFactor[];
}

interface CrossAssetRow {
  key: string;
  name: string;
  correlation_30d: number;
  relevance: 'ALTA' | 'MEDIA' | 'BAIXA';
  direction: 'CONFIRMANDO' | 'DIVERGINDO' | null;
  change_pct_latest: number | null;
}

interface RegimeReport {
  symbol: string;
  local_regime: LocalRegime | null;
  macro_context: 'POSITIVO' | 'NEUTRO' | 'NEGATIVO';
  cross_asset_relevance: CrossAssetRow[];
}

interface MacroInstrument {
  key: string;
  symbol: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  taken_at: string | null;
}

interface MacroOverview {
  instruments: MacroInstrument[];
  nasdaq_cross_asset_relevance: CrossAssetRow[];
}

const REGIME_CLASS: Record<string, string> = {
  'STRONG BULL': 'up',
  BULL: 'up',
  NEUTRAL: '',
  BEAR: 'down',
  'STRONG BEAR': 'down',
};

function fmtPct(value: number | null) {
  if (value === null || value === undefined) return '-';
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

export function Regime() {
  const [symbol, setSymbol] = useState('NASDAQ');
  const [symbolInput, setSymbolInput] = useState('NASDAQ');
  const [report, setReport] = useState<RegimeReport | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const { data: macro, lastUpdated } = usePolling<MacroOverview>('/api/regime/macro', 60000);

  async function loadReport(targetSymbol: string) {
    setReportError(null);
    try {
      const result = await api.get<RegimeReport>(`/api/regime/${encodeURIComponent(targetSymbol)}`);
      setReport(result);
    } catch (err) {
      setReport(null);
      setReportError(err instanceof Error ? err.message : 'Erro ao buscar regime');
    }
  }

  useEffect(() => {
    loadReport(symbol);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const next = symbolInput.trim().toUpperCase();
    if (!next) return;
    setSymbol(next);
    loadReport(next);
  }

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <p className="eyebrow">Regime de mercado</p>
          <h1>Regime Engine</h1>
          <p className="muted">
            Estado local (tendência/momentum/volatilidade/estrutura) de um ativo, combinado com o
            contexto macro/cross-asset — leitura determinística, sem IA envolvida no cálculo.
          </p>
        </div>
      </div>

      <section className="panel">
        <form onSubmit={handleSubmit} className="inline-form">
          <input
            value={symbolInput}
            onChange={(e) => setSymbolInput(e.target.value)}
            placeholder="Ex: NASDAQ, AAPL, GOLD, SP500"
          />
          <button type="submit">Ver regime</button>
        </form>

        {reportError && <p className="muted">{reportError}</p>}

        {report && (
          <div className="regime-card">
            <div className="regime-card-header">
              <h2>{report.symbol}</h2>
              {report.local_regime ? (
                <span className={`pill ${REGIME_CLASS[report.local_regime.label] ?? ''}`}>
                  {report.local_regime.label} ({report.local_regime.score})
                </span>
              ) : (
                <span className="muted">Sem histórico suficiente</span>
              )}
              <span className={`pill ${report.macro_context === 'POSITIVO' ? 'up' : report.macro_context === 'NEGATIVO' ? 'down' : ''}`}>
                Macro: {report.macro_context}
              </span>
            </div>

            {report.local_regime && report.local_regime.factors.length > 0 && (
              <ul className="compact-list">
                {report.local_regime.factors.map((f, i) => (
                  <li key={i}>
                    <span className="mini-symbol">{f.impact !== null ? `${f.impact > 0 ? '+' : ''}${f.impact}` : '-'}</span>
                    <div>
                      <strong>{f.name}</strong>
                      <span>{f.evidence}</span>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {report.cross_asset_relevance.length > 0 && (
              <div className="table-scroll compact-scroll">
                <table className="table dense-table">
                  <thead>
                    <tr>
                      <th>Instrumento</th>
                      <th>Correlação 30d</th>
                      <th>Relevância</th>
                      <th>Direção</th>
                      <th>Variação recente</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.cross_asset_relevance.map((row) => (
                      <tr key={row.key}>
                        <td>{row.name}</td>
                        <td>{row.correlation_30d.toFixed(2)}</td>
                        <td>{row.relevance}</td>
                        <td>{row.direction ?? '-'}</td>
                        <td className={(row.change_pct_latest ?? 0) >= 0 ? 'up' : 'down'}>
                          {fmtPct(row.change_pct_latest)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Universo macro monitorado</h2>
          {lastUpdated && <span className="muted">Atualizado {lastUpdated.toLocaleTimeString('pt-BR')}</span>}
        </div>
        <div className="table-scroll compact-scroll">
          <table className="table dense-table">
            <thead>
              <tr>
                <th>Instrumento</th>
                <th>Símbolo</th>
                <th>Preço</th>
                <th>Variação</th>
              </tr>
            </thead>
            <tbody>
              {!macro || macro.instruments.length === 0 ? (
                <tr>
                  <td colSpan={4} className="muted">
                    Ainda sem snapshots — aguarde o próximo ciclo do coletor macro.
                  </td>
                </tr>
              ) : (
                macro.instruments.map((inst) => (
                  <tr key={inst.key}>
                    <td>{inst.name}</td>
                    <td className="muted">{inst.symbol}</td>
                    <td>{inst.price !== null ? inst.price.toFixed(2) : '-'}</td>
                    <td className={(inst.change_pct ?? 0) >= 0 ? 'up' : 'down'}>{fmtPct(inst.change_pct)}</td>
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
