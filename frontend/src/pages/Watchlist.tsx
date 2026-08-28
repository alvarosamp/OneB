import { Fragment, useEffect, useMemo, useState, type FormEvent } from 'react';
import { api, ApiError } from '../api/client';
import { useToast } from '../context/ToastContext';
import { useConfirm } from '../components/ConfirmModal';
import { RuleConditionBuilder } from '../components/RuleConditionBuilder';
import { useRuleConditions } from '../hooks/useRuleConditions';
import { usePolling } from '../hooks/usePolling';
import type { AssetType, BacktestResult, WatchlistItem, WatchlistPrice } from '../types';

const assetTypeLabels: Record<AssetType, string> = {
  equity: 'Acao',
  etf: 'ETF',
  index: 'Indice',
  commodity: 'Commodity',
  fx: 'Cambio',
  bond_yield: 'Juros',
  macro: 'Macro',
};

function minutesSince(iso: string | null) {
  if (!iso) return null;
  return Math.round((Date.now() - new Date(iso).getTime()) / 60000);
}

function priceConfidence(quote: WatchlistPrice | undefined) {
  if (!quote || quote.price === null) return { cls: 'low', label: 'Sem dado' };
  const age = minutesSince(quote.taken_at);
  if (age === null) return { cls: 'low', label: 'Sem dado' };
  if (age <= 5) return { cls: 'high', label: 'Ao vivo' };
  if (age <= 30) return { cls: 'mid', label: `${age} min` };
  return { cls: 'low', label: `${age} min` };
}

export function Watchlist() {
  const toast = useToast();
  const confirm = useConfirm();
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const { data: prices, lastUpdated } = usePolling<WatchlistPrice[]>('/api/watchlist/prices', 20000);
  const priceById = useMemo(() => {
    const map = new Map<number, WatchlistPrice>();
    (prices ?? []).forEach((p) => map.set(p.id, p));
    return map;
  }, [prices]);
  const [symbol, setSymbol] = useState('');
  const [label, setLabel] = useState('');
  const [assetType, setAssetType] = useState<AssetType>('equity');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [backtesting, setBacktesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const builder = useRuleConditions();

  async function loadItems() {
    try {
      setItems(await api.get<WatchlistItem[]>('/api/watchlist'));
    } catch {
      toast('Erro ao carregar watchlist', 'error');
    }
  }

  useEffect(() => {
    loadItems();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleAdd(e: FormEvent) {
    e.preventDefault();
    try {
      await api.post('/api/watchlist', { symbol, label, asset_type: assetType });
      toast(`${symbol.toUpperCase()} adicionado à watchlist`, 'success');
      setSymbol('');
      setLabel('');
      setAssetType('equity');
      loadItems();
    } catch {
      toast('Erro ao adicionar ativo', 'error');
    }
  }

  async function handleRemove(item: WatchlistItem) {
    const ok = await confirm(`Remover ${item.symbol} da watchlist? Isso também remove as regras associadas.`);
    if (!ok) return;
    try {
      await api.delete(`/api/watchlist/${item.id}`);
      toast(`${item.symbol} removido`, 'success');
      loadItems();
    } catch {
      toast('Erro ao remover ativo', 'error');
    }
  }

  function openRuleForm(item: WatchlistItem) {
    setExpandedId(item.id);
    setBacktestResult(null);
    builder.reset();
  }

  async function handleTestRule(item: WatchlistItem) {
    setBacktesting(true);
    setBacktestResult(null);
    try {
      const result = await api.post<BacktestResult>('/api/watchlist/rules/backtest', {
        symbol: item.symbol,
        logic: builder.logic,
        conditions: builder.conditions,
        period: '3mo',
        interval: '1d',
        forward_bars: 5,
      });
      setBacktestResult(result);
    } catch {
      toast('Erro ao testar regra', 'error');
    } finally {
      setBacktesting(false);
    }
  }

  async function handleSaveRule(item: WatchlistItem) {
    if (builder.conditions.length === 0) {
      toast('Adicione ao menos uma condição', 'error');
      return;
    }
    setSaving(true);
    try {
      await api.post(`/api/watchlist/${item.id}/rules`, {
        watchlist_item_id: item.id,
        logic: builder.logic,
        cooldown_minutes: builder.cooldownMinutes,
        conditions: builder.conditions,
      });
      toast(`Regra criada para ${item.symbol}`, 'success');
      setExpandedId(null);
      setBacktestResult(null);
      builder.reset();
      await loadItems();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Erro ao criar regra', 'error');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <p className="eyebrow">Monitoramento</p>
          <h1>Watchlist &amp; Regras de Alerta</h1>
          <p className="muted">Ativos acompanhados, preço em tempo quase real e regras de disparo por ativo.</p>
        </div>
      </div>

      <section className="panel">
        <h2>Adicionar ativo</h2>
        <form onSubmit={handleAdd}>
          <input
            type="text"
            placeholder="Símbolo (ex: AAPL, GLD, GC=F)"
            required
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
          />
          <input type="text" placeholder="Rótulo (opcional)" value={label} onChange={(e) => setLabel(e.target.value)} />
          <select value={assetType} onChange={(e) => setAssetType(e.target.value as AssetType)}>
            {Object.entries(assetTypeLabels).map(([value, text]) => (
              <option key={value} value={value}>
                {text}
              </option>
            ))}
          </select>
          <button type="submit">Adicionar</button>
        </form>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Ativos monitorados</h2>
          {lastUpdated && <span className="muted">Atualizado {lastUpdated.toLocaleTimeString('pt-BR')}</span>}
        </div>
        <div className="table-scroll">
          <table className="table dense-table">
            <thead>
              <tr>
                <th>Ativo</th>
                <th>Tipo</th>
                <th>Preço</th>
                <th>Variação</th>
                <th>Confiabilidade do dado</th>
                <th>Status</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr>
                  <td colSpan={7} className="muted">
                    Nenhum ativo cadastrado ainda.
                  </td>
                </tr>
              )}
              {items.map((item) => {
                const quote = priceById.get(item.id);
                const confidence = priceConfidence(quote);
                return (
                <Fragment key={item.id}>
                  <tr>
                    <td>
                      <strong>{item.symbol}</strong> {item.label && <span className="muted">{item.label}</span>}
                    </td>
                    <td>{assetTypeLabels[item.asset_type] ?? item.asset_type}</td>
                    <td>{quote?.price != null ? quote.price.toFixed(2) : '-'}</td>
                    <td className={quote?.change_pct != null ? (quote.change_pct >= 0 ? 'up' : 'down') : undefined}>
                      {quote?.change_pct != null ? `${quote.change_pct >= 0 ? '+' : ''}${quote.change_pct.toFixed(2)}%` : '-'}
                    </td>
                    <td>
                      <span className={`confidence ${confidence.cls}`}>
                        <i />
                        {confidence.label}
                      </span>
                    </td>
                    <td>
                      <span className={`status-pill ${item.active ? 'good' : 'warn'}`}>
                        {item.active ? 'Ativo' : 'Inativo'}
                      </span>
                    </td>
                    <td>
                      <button type="button" className="link-btn" onClick={() => openRuleForm(item)}>
                        + regra
                      </button>
                      <button type="button" className="link-btn danger" onClick={() => handleRemove(item)}>
                        remover
                      </button>
                    </td>
                  </tr>
                  {expandedId === item.id && (
                    <tr>
                      <td colSpan={7}>
                        <div className="rule-form">
                          <RuleConditionBuilder builder={builder} />
                          <div className="chart-controls">
                            <button
                              type="button"
                              className="btn-secondary"
                              disabled={backtesting}
                              onClick={() => handleTestRule(item)}
                            >
                              {backtesting ? 'Testando...' : 'Testar regra'}
                            </button>
                            <button type="button" disabled={saving} onClick={() => handleSaveRule(item)}>
                              {saving ? 'Salvando...' : 'Salvar regra'}
                            </button>
                          </div>
                          {backtestResult && (
                            <div className="metric-mini-grid">
                              <div><span>Disparos</span><strong>{backtestResult.trigger_count}</strong></div>
                              <div><span>Retorno medio</span><strong>{backtestResult.avg_forward_return_pct === null ? '-' : `${backtestResult.avg_forward_return_pct.toFixed(2)}%`}</strong></div>
                              <div><span>Acerto</span><strong>{backtestResult.win_rate_pct === null ? '-' : `${backtestResult.win_rate_pct.toFixed(1)}%`}</strong></div>
                              <div><span>Profit factor</span><strong>{backtestResult.profit_factor === null ? '-' : backtestResult.profit_factor === 999 ? 'sem perdas' : backtestResult.profit_factor.toFixed(2)}</strong></div>
                              <div><span>Drawdown</span><strong>{backtestResult.max_drawdown_pct === null ? '-' : `${backtestResult.max_drawdown_pct.toFixed(2)}%`}</strong></div>
                              <div><span>Buy & hold</span><strong>{backtestResult.buy_hold_return_pct === null ? '-' : `${backtestResult.buy_hold_return_pct.toFixed(2)}%`}</strong></div>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
