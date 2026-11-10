import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { api } from '../api/client';
import { CandlestickChart } from '../components/CandlestickChart';
import { useToast } from '../context/ToastContext';
import type { ChartData, TechnicalAnalysis, TechnicalEdgeRanking, TechnicalLevel, TradeSetup, WatchlistItem } from '../types';

function fmtMoney(value: number | null | undefined) {
  if (value === null || value === undefined) return '-';
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'USD' });
}

function fmtNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined) return '-';
  return value.toLocaleString('pt-BR', { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function fmtVolume(value: number | null | undefined) {
  if (value === null || value === undefined) return '-';
  return value.toLocaleString('pt-BR', { maximumFractionDigits: 0 });
}

function setupRiskReward(setup: TradeSetup) {
  const risk = Math.abs(setup.entry_price - setup.stop_price);
  const reward = Math.abs(setup.target_price - setup.entry_price);
  if (risk === 0) return null;
  return reward / risk;
}

const PERIOD_OPTIONS = [
  { value: '1d', label: '1D' },
  { value: '5d', label: '5D' },
  { value: '1mo', label: '1M' },
  { value: '3mo', label: '3M' },
];

const INTERVAL_OPTIONS = [
  { value: '5m', label: '5m' },
  { value: '15m', label: '15m' },
  { value: '1h', label: '1h' },
  { value: '1d', label: '1D' },
];

const defaultLevelColor: Record<string, string> = {
  SUPPORT: '#22c55e',
  RESISTANCE: '#ef4444',
  TARGET: '#f59e0b',
  ENTRY: '#60a5fa',
  STOP: '#f43f5e',
  ZONE: '#a78bfa',
};

export function MesaTecnica() {
  const toast = useToast();
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [symbol, setSymbol] = useState('');
  const [period, setPeriod] = useState('5d');
  const [interval, setInterval_] = useState('15m');
  const [data, setData] = useState<ChartData | null>(null);
  const [analysis, setAnalysis] = useState<TechnicalAnalysis | null>(null);
  const [research, setResearch] = useState<TechnicalEdgeRanking | null>(null);
  const [status, setStatus] = useState('Carregando favoritos...');
  const [levelForm, setLevelForm] = useState({ label: '', kind: 'ZONE', price: '', notes: '' });
  const [setupForm, setSetupForm] = useState({
    direction: 'LONG',
    entry_price: '',
    stop_price: '',
    target_price: '',
    thesis: '',
    invalidation: '',
  });

  useEffect(() => {
    let cancelled = false;
    api
      .get<WatchlistItem[]>('/api/watchlist')
      .then((watchlist) => {
        if (cancelled) return;
        setItems(watchlist);
        setSymbol((current) => current || watchlist[0]?.symbol || 'AAPL');
        const universe = Array.from(new Set([...watchlist.map((item) => item.symbol), 'AAPL', 'MSFT', 'NVDA'])).slice(0, 50);
        if (universe.length >= 3) {
          api.get<TechnicalEdgeRanking>(`/api/technical/edge?symbols=${encodeURIComponent(universe.join(','))}`).then(setResearch).catch(() => setResearch(null));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSymbol('AAPL');
          setStatus('Nao consegui carregar a watchlist. Usando AAPL.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function loadSymbol(nextSymbol = symbol) {
    if (!nextSymbol) return;
    const encoded = encodeURIComponent(nextSymbol);
    const [chart, technical] = await Promise.all([
      api.get<ChartData>(`/api/chart/${encoded}?period=${period}&interval=${interval}`),
      api.get<TechnicalAnalysis>(`/api/technical/analysis/${encoded}?period=${period}&interval=${interval}`),
    ]);
    setData(chart);
    setAnalysis(technical);
    setStatus(`Atualizado ${new Date().toLocaleTimeString('pt-BR')}`);
  }

  useEffect(() => {
    if (!symbol) return;
    let cancelled = false;

    async function run() {
      try {
        await loadSymbol(symbol);
      } catch {
        if (!cancelled) {
          setData(null);
          setAnalysis(null);
          setStatus('Erro ao carregar historico do ativo.');
        }
      }
    }

    run();
    const timer = setInterval(run, 30000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [interval, period, symbol]);

  const chartLevels = useMemo(() => {
    const autoLevels = [
      analysis?.support ? { label: 'Suporte auto', value: analysis.support, color: '#22c55e' } : null,
      analysis?.pivot ? { label: 'Media 20', value: analysis.pivot, color: '#f59e0b' } : null,
      analysis?.resistance ? { label: 'Resistencia auto', value: analysis.resistance, color: '#ef4444' } : null,
      analysis?.price ? { label: 'Preco', value: analysis.price, color: '#60a5fa' } : null,
    ].filter((level): level is { label: string; value: number; color: string } => level !== null);
    const savedLevels =
      analysis?.levels.map((level) => ({ label: level.label, value: level.price, color: level.color })) ?? [];
    const setupLevels =
      analysis?.setups.flatMap((setup) => [
        { label: `Entrada ${setup.id}`, value: setup.entry_price, color: defaultLevelColor.ENTRY },
        { label: `Stop ${setup.id}`, value: setup.stop_price, color: defaultLevelColor.STOP },
        { label: `Alvo ${setup.id}`, value: setup.target_price, color: defaultLevelColor.TARGET },
      ]) ?? [];
    return [...autoLevels, ...savedLevels, ...setupLevels];
  }, [analysis]);

  async function handleCreateLevel(e: FormEvent) {
    e.preventDefault();
    const price = Number(levelForm.price);
    if (!symbol || !Number.isFinite(price) || price <= 0) {
      toast('Informe um preco valido para o nivel', 'error');
      return;
    }
    try {
      await api.post<TechnicalLevel>('/api/technical/levels', {
        symbol,
        label: levelForm.label || levelForm.kind,
        kind: levelForm.kind,
        price,
        color: defaultLevelColor[levelForm.kind] ?? defaultLevelColor.ZONE,
        notes: levelForm.notes,
      });
      setLevelForm({ label: '', kind: 'ZONE', price: '', notes: '' });
      await loadSymbol();
      toast('Nivel salvo no estudo', 'success');
    } catch {
      toast('Erro ao salvar nivel', 'error');
    }
  }

  async function quickLevel(kind: string, price: number | null | undefined) {
    if (!price) return;
    setLevelForm((current) => ({ ...current, kind, price: String(price), label: kind }));
  }

  async function deleteLevel(level: TechnicalLevel) {
    try {
      await api.delete(`/api/technical/levels/${level.id}`);
      await loadSymbol();
      toast('Nivel removido', 'success');
    } catch {
      toast('Erro ao remover nivel', 'error');
    }
  }

  async function handleCreateSetup(e: FormEvent) {
    e.preventDefault();
    const payload = {
      symbol,
      direction: setupForm.direction,
      entry_price: Number(setupForm.entry_price),
      stop_price: Number(setupForm.stop_price),
      target_price: Number(setupForm.target_price),
      thesis: setupForm.thesis,
      invalidation: setupForm.invalidation,
    };
    if ([payload.entry_price, payload.stop_price, payload.target_price].some((value) => !Number.isFinite(value))) {
      toast('Preencha entrada, stop e alvo', 'error');
      return;
    }
    try {
      await api.post<TradeSetup>('/api/technical/setups', payload);
      setSetupForm({ direction: 'LONG', entry_price: '', stop_price: '', target_price: '', thesis: '', invalidation: '' });
      await loadSymbol();
      toast('Plano salvo', 'success');
    } catch {
      toast('Erro ao salvar plano', 'error');
    }
  }

  async function archiveSetup(setup: TradeSetup) {
    try {
      await api.delete(`/api/technical/setups/${setup.id}`);
      await loadSymbol();
      toast('Plano arquivado', 'success');
    } catch {
      toast('Erro ao arquivar plano', 'error');
    }
  }

  const selectedItem = items.find((item) => item.symbol === symbol);

  return (
    <div className="technical-desk">
      <aside className="technical-sidebar">
        <div>
          <p className="eyebrow">Mesa tecnica</p>
          <h1>Mesa Técnica</h1>
          <span className="muted">{status}</span>
        </div>

        <div className="technical-search">
          <label className="field-label">
            Ativo
            <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} placeholder="AAPL" />
          </label>
        </div>

        <div className="technical-favorites">
          {items.length === 0 && <span className="muted">Cadastre ativos na Watchlist para preencher favoritos.</span>}
          {items.map((item) => (
            <button
              type="button"
              key={item.id}
              className={item.symbol === symbol ? 'active' : ''}
              onClick={() => setSymbol(item.symbol)}
            >
              <strong>{item.symbol}</strong>
              <span>{item.label || 'Sem rotulo'}</span>
            </button>
          ))}
        </div>
      </aside>

      <section className="technical-main">
        <div className="technical-toolbar">
          <div>
            <h2>{symbol}</h2>
            <span className="muted">{selectedItem?.label || analysis?.trend || 'Leitura tecnica'}</span>
          </div>
          <div className="technical-controls">
            <div className="segmented-control" role="group" aria-label="Periodo">
              {PERIOD_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  className={`segmented-option${period === opt.value ? ' active' : ''}`}
                  onClick={() => setPeriod(opt.value)}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <div className="segmented-control" role="group" aria-label="Intervalo">
              {INTERVAL_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  className={`segmented-option${interval === opt.value ? ' active' : ''}`}
                  onClick={() => setInterval_(opt.value)}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="technical-tape">
          <div>
            <span>Preco</span>
            <strong>{fmtMoney(analysis?.price)}</strong>
          </div>
          <div>
            <span>Variacao candle</span>
            <strong className={analysis?.change_pct !== null && (analysis?.change_pct ?? 0) >= 0 ? 'up' : 'down'}>
              {analysis?.change_pct === null || analysis?.change_pct === undefined
                ? '-'
                : `${analysis.change_pct >= 0 ? '+' : ''}${analysis.change_pct.toFixed(2)}%`}
            </strong>
          </div>
          <div>
            <span>Vies</span>
            <strong>{analysis?.bias ?? '-'}</strong>
          </div>
          <div>
            <span>Risco/Retorno</span>
            <strong>{analysis?.risk_reward ? `${analysis.risk_reward.toFixed(2)}R` : '-'}</strong>
          </div>
          <div>
            <span>Volatilidade</span>
            <strong>{analysis?.volatility_label ?? '-'}</strong>
          </div>
          <div>
            <span>ATR14</span>
            <strong>
              {fmtMoney(analysis?.atr_14)} {analysis?.atr_pct ? `(${analysis.atr_pct.toFixed(2)}%)` : ''}
            </strong>
          </div>
        </div>

        <div className="technical-chart-panel">
          {data ? <CandlestickChart data={data} symbol={symbol} levels={chartLevels} compact /> : <p>{status}</p>}
        </div>
      </section>

      <aside className="technical-study">
        <h2>Estudo</h2>
        <div className="study-card">
          <span>Leitura</span>
          <strong>{analysis?.trend ?? 'Aguardando dados'}</strong>
        </div>
        <div className="study-card">
          <span>RSI / Volume medio 20</span>
          <strong>
            {fmtNumber(analysis?.rsi)} / {fmtVolume(analysis?.avg_volume_20)}
          </strong>
        </div>
        <div className="volatility-grid">
          <div>
            <span>Vol. anual 20</span>
            <strong>{analysis?.annualized_volatility_20 ? `${analysis.annualized_volatility_20.toFixed(2)}%` : '-'}</strong>
          </div>
          <div>
            <span>Range medio</span>
            <strong>{analysis?.avg_range_pct_20 ? `${analysis.avg_range_pct_20.toFixed(2)}%` : '-'}</strong>
          </div>
          <div>
            <span>Ate suporte</span>
            <strong>{analysis?.distance_to_support_pct ? `${analysis.distance_to_support_pct.toFixed(2)}%` : '-'}</strong>
          </div>
          <div>
            <span>Ate resistencia</span>
            <strong>{analysis?.distance_to_resistance_pct ? `+${analysis.distance_to_resistance_pct.toFixed(2)}%` : '-'}</strong>
          </div>
          <div>
            <span>Lote US$ 200</span>
            <strong>{analysis?.suggested_shares_200_usd ?? 0} acoes</strong>
          </div>
          <div>
            <span>Risco 1 ATR</span>
            <strong>{fmtMoney(analysis?.suggested_risk_usd_200)}</strong>
          </div>
        </div>

        <div className="technical-quick-actions">
          <button type="button" onClick={() => quickLevel('SUPPORT', analysis?.support)}>Suporte</button>
          <button type="button" onClick={() => quickLevel('RESISTANCE', analysis?.resistance)}>Resistencia</button>
          <button type="button" onClick={() => quickLevel('ENTRY', analysis?.price)}>Entrada</button>
        </div>

        <form className="technical-form" onSubmit={handleCreateLevel}>
          <label className="field-label">
            Tipo
            <select value={levelForm.kind} onChange={(e) => setLevelForm({ ...levelForm, kind: e.target.value })}>
              <option value="ZONE">Zona</option>
              <option value="SUPPORT">Suporte</option>
              <option value="RESISTANCE">Resistencia</option>
              <option value="ENTRY">Entrada</option>
              <option value="TARGET">Alvo</option>
              <option value="STOP">Stop</option>
            </select>
          </label>
          <label className="field-label">
            Preco
            <input value={levelForm.price} onChange={(e) => setLevelForm({ ...levelForm, price: e.target.value })} />
          </label>
          <label className="field-label">
            Rotulo
            <input value={levelForm.label} onChange={(e) => setLevelForm({ ...levelForm, label: e.target.value })} />
          </label>
          <label className="field-label">
            Nota
            <textarea value={levelForm.notes} onChange={(e) => setLevelForm({ ...levelForm, notes: e.target.value })} />
          </label>
          <button type="submit">Salvar nivel</button>
        </form>

        <div className="level-list">
          {(analysis?.levels ?? []).map((level) => (
            <div key={level.id}>
              <span style={{ borderColor: level.color }}>{level.label}</span>
              <strong>{fmtMoney(level.price)}</strong>
              <button type="button" onClick={() => deleteLevel(level)}>x</button>
            </div>
          ))}
        </div>

        <form className="technical-form" onSubmit={handleCreateSetup}>
          <h3>Plano</h3>
          <label className="field-label">
            Direcao
            <select value={setupForm.direction} onChange={(e) => setSetupForm({ ...setupForm, direction: e.target.value })}>
              <option value="LONG">Compra</option>
              <option value="SHORT">Venda</option>
            </select>
          </label>
          <label className="field-label">
            Entrada
            <input value={setupForm.entry_price} onChange={(e) => setSetupForm({ ...setupForm, entry_price: e.target.value })} />
          </label>
          <label className="field-label">
            Stop
            <input value={setupForm.stop_price} onChange={(e) => setSetupForm({ ...setupForm, stop_price: e.target.value })} />
          </label>
          <label className="field-label">
            Alvo
            <input value={setupForm.target_price} onChange={(e) => setSetupForm({ ...setupForm, target_price: e.target.value })} />
          </label>
          <label className="field-label">
            Tese
            <textarea value={setupForm.thesis} onChange={(e) => setSetupForm({ ...setupForm, thesis: e.target.value })} />
          </label>
          <label className="field-label">
            Invalidacao
            <textarea value={setupForm.invalidation} onChange={(e) => setSetupForm({ ...setupForm, invalidation: e.target.value })} />
          </label>
          <button type="submit">Salvar plano</button>
        </form>

        <div className="setup-list">
          {(analysis?.setups ?? []).map((setup) => (
            <article key={setup.id}>
              <div>
                <strong>{setup.direction}</strong>
                <span>{setupRiskReward(setup)?.toFixed(2) ?? '-'}R</span>
              </div>
              <p>
                Entrada {fmtMoney(setup.entry_price)} | Stop {fmtMoney(setup.stop_price)} | Alvo{' '}
                {fmtMoney(setup.target_price)}
              </p>
              {setup.thesis && <p>{setup.thesis}</p>}
              <button type="button" onClick={() => archiveSetup(setup)}>Arquivar</button>
            </article>
          ))}
        </div>

        <div className="signal-list">
          {(analysis?.signals ?? []).map((signal) => (
            <div key={signal.name} className={`signal-row ${signal.state}`}>
              <strong>{signal.label}</strong>
              <span>{signal.evidence}</span>
            </div>
          ))}
        </div>

        <section className="study-card">
          <span>Pesquisa experimental · 5 pregões</span>
          <p className="muted">Ranking cross-sectional, separado da leitura operacional e sem ordem automática.</p>
          {research?.rows.slice(0, 5).map((row) => (
            <div key={row.symbol} className="signal-row neutral">
              <strong>#{row.rank ?? '-'} {row.symbol}</strong>
              <span>{row.status === 'OK' ? `${row.label} · score ${row.edge_score}` : 'Sem leitura'}</span>
            </div>
          ))}
          {research && <small>{research.research_note}</small>}
        </section>
      </aside>
    </div>
  );
}
