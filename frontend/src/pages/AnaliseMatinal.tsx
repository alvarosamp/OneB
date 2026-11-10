import { useEffect, useState } from 'react';
import { api, fetchBlob } from '../api/client';
import { useToast } from '../context/ToastContext';
import type { MorningReport, MorningReportIndex, MorningReportWatchlistRow, SymbolLevels } from '../types';

function fmtDateTime(iso: string) {
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function LevelsRow({ levels }: { levels: SymbolLevels | null }) {
  if (!levels) return <span className="muted">sem niveis</span>;
  const { pivots } = levels;
  return (
    <span className="muted block-text">
      P {pivots.pivot} · R1 {pivots.r1} / R2 {pivots.r2} · S1 {pivots.s1} / S2 {pivots.s2}
    </span>
  );
}

function IndexCard({ idx }: { idx: MorningReportIndex }) {
  const up = idx.change_pct >= 0;
  return (
    <div className="metric-card">
      <span className="metric-label">{idx.name}</span>
      <strong className={up ? 'up' : 'down'}>
        {idx.price.toFixed(2)} {up ? '▲' : '▼'} {idx.change_pct.toFixed(2)}%
      </strong>
      <LevelsRow levels={idx.levels} />
    </div>
  );
}

function WatchlistRow({ row }: { row: MorningReportWatchlistRow }) {
  const hasData = row.price !== null;
  const up = (row.change_pct ?? 0) >= 0;
  return (
    <tr>
      <td>{row.symbol}</td>
      <td>{hasData ? row.price!.toFixed(2) : '-'}</td>
      <td className={hasData ? (up ? 'up' : 'down') : ''}>
        {hasData ? `${row.change_pct!.toFixed(2)}%` : '-'}
      </td>
      <td>
        <LevelsRow levels={row.levels} />
      </td>
    </tr>
  );
}

export function AnaliseMatinal() {
  const [history, setHistory] = useState<MorningReport[]>([]);
  const [selected, setSelected] = useState<MorningReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const toast = useToast();

  async function loadAll() {
    setLoading(true);
    try {
      const [t, h] = await Promise.allSettled([
        api.get<MorningReport>('/api/morning-report/today'),
        api.get<MorningReport[]>('/api/morning-report/history?limit=14'),
      ]);
      const todayReport = t.status === 'fulfilled' ? t.value : null;
      setSelected(todayReport);
      setHistory(h.status === 'fulfilled' ? h.value : []);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function handleGenerate() {
    setGenerating(true);
    try {
      const report = await api.post<MorningReport>('/api/morning-report/generate');
      setSelected(report);
      setHistory((prev) => [report, ...prev.filter((r) => r.id !== report.id)]);
      toast('Analise matinal gerada.', 'success');
    } catch {
      toast('Erro ao gerar a analise matinal.', 'error');
    } finally {
      setGenerating(false);
    }
  }

  async function handleDownloadPdf(id: number) {
    setDownloading(true);
    try {
      const blob = await fetchBlob(`/api/morning-report/${id}/pdf`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `analise-matinal-${id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast('Erro ao gerar o PDF.', 'error');
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="container dashboard-container">
      <div className="page-header">
        <div>
          <p className="eyebrow">Pre-mercado</p>
          <h1>Analise Matinal</h1>
          <p className="muted">
            Nasdaq, S&amp;P/NYSE e Ouro com niveis de pivot (suporte/resistencia), watchlist, noticias
            da madrugada e calendario do dia — gerado automaticamente todo dia util antes da abertura.
          </p>
        </div>
        <button type="button" onClick={handleGenerate} disabled={generating}>
          {generating ? 'Gerando...' : 'Gerar agora'}
        </button>
      </div>

      {loading ? (
        <p className="muted">Carregando...</p>
      ) : !selected ? (
        <p className="muted">Nenhuma analise matinal gerada ainda. Clique em "Gerar agora".</p>
      ) : (
        <>
          <section className="panel">
            <div className="panel-title">
              <h2>Indices e commodities</h2>
              <span className="muted">gerado {fmtDateTime(selected.generated_at)}</span>
            </div>
            <div className="metric-grid">
              {selected.data.indices.map((idx) => (
                <IndexCard key={idx.key} idx={idx} />
              ))}
            </div>
          </section>

          <section className="panel">
            <h2>Watchlist</h2>
            <div className="table-scroll compact-scroll">
              <table className="table dense-table">
                <thead>
                  <tr>
                    <th>Simbolo</th>
                    <th>Preco</th>
                    <th>Variacao</th>
                    <th>Niveis (pivot)</th>
                  </tr>
                </thead>
                <tbody>
                  {selected.data.watchlist.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="muted">
                        Watchlist vazia.
                      </td>
                    </tr>
                  ) : (
                    selected.data.watchlist.map((row) => <WatchlistRow key={row.symbol} row={row} />)
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel">
            <h2>Leitura do dia</h2>
            <pre className="morning-report-narrative">{selected.narrative}</pre>
            <button type="button" onClick={() => handleDownloadPdf(selected.id)} disabled={downloading}>
              {downloading ? 'Gerando PDF...' : 'Baixar PDF desta analise'}
            </button>
          </section>

          {history.length > 1 && (
            <section className="panel">
              <h2>Historico</h2>
              <ul className="compact-list">
                {history.map((r) => (
                  <li key={r.id}>
                    <span className="mini-symbol">{r.id === selected.id ? 'atual' : 'ver'}</span>
                    <div>
                      <button type="button" className="link-btn" onClick={() => setSelected(r)}>
                        {fmtDateTime(r.generated_at)}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
