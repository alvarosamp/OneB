import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../api/client';
import { useToast } from '../context/ToastContext';
import { useConfirm } from '../components/ConfirmModal';
import type { PositionSummary, Transaction, TransactionSide } from '../types';

function fmt(v: number | null | undefined, decimals = 2) {
  return v === null || v === undefined ? '-' : v.toFixed(decimals);
}

export function Posicoes() {
  const toast = useToast();
  const confirm = useConfirm();
  const [positions, setPositions] = useState<PositionSummary[]>([]);
  const [history, setHistory] = useState<Transaction[]>([]);
  const [historySymbol, setHistorySymbol] = useState<string | null>(null);

  const [symbol, setSymbol] = useState('');
  const [side, setSide] = useState<TransactionSide>('BUY');
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [executedAt, setExecutedAt] = useState('');
  const [notes, setNotes] = useState('');

  async function loadPositions() {
    try {
      setPositions(await api.get<PositionSummary[]>('/api/positions'));
    } catch {
      toast('Erro ao carregar posições', 'error');
    }
  }

  useEffect(() => {
    loadPositions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function showHistory(sym: string) {
    setHistorySymbol(sym);
    try {
      setHistory(await api.get<Transaction[]>(`/api/positions/${sym}/transactions`));
    } catch {
      toast('Erro ao carregar histórico', 'error');
    }
  }

  async function handleDeleteTransaction(id: number) {
    const ok = await confirm('Remover essa transação?');
    if (!ok || !historySymbol) return;
    try {
      await api.delete(`/api/positions/transactions/${id}`);
      toast('Transação removida', 'success');
      showHistory(historySymbol);
      loadPositions();
    } catch {
      toast('Erro ao remover transação', 'error');
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const symbolUpper = symbol.trim().toUpperCase();
    try {
      await api.post('/api/positions/transactions', {
        symbol: symbolUpper,
        side,
        quantity: parseFloat(quantity),
        price: parseFloat(price),
        executed_at: new Date(executedAt).toISOString(),
        notes,
      });
      toast(`Transação registrada para ${symbolUpper}`, 'success');
      setSymbol('');
      setQuantity('');
      setPrice('');
      setExecutedAt('');
      setNotes('');
      loadPositions();
    } catch {
      toast('Erro ao registrar transação', 'error');
    }
  }

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <p className="eyebrow">Lançamento manual</p>
          <h1>Posições &amp; P&amp;L</h1>
          <p className="muted">
            Registro manual de compras/vendas — não integra com nenhuma corretora nem executa nada, é
            só contabilidade pra você acompanhar o resultado do que já operou (ex: na Exness).
          </p>
        </div>
      </div>

      <section className="panel">
        <h2>Registrar transação</h2>
        <form onSubmit={handleSubmit}>
          <input type="text" placeholder="Símbolo (ex: AAPL)" required value={symbol} onChange={(e) => setSymbol(e.target.value)} />
          <select value={side} onChange={(e) => setSide(e.target.value as TransactionSide)}>
            <option value="BUY">Compra</option>
            <option value="SELL">Venda</option>
          </select>
          <input
            type="number"
            step="0.0001"
            placeholder="Quantidade"
            required
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
          />
          <input
            type="number"
            step="0.01"
            placeholder="Preço (US$)"
            required
            value={price}
            onChange={(e) => setPrice(e.target.value)}
          />
          <input type="datetime-local" required value={executedAt} onChange={(e) => setExecutedAt(e.target.value)} />
          <input type="text" placeholder="Nota (opcional)" value={notes} onChange={(e) => setNotes(e.target.value)} />
          <button type="submit">Registrar</button>
        </form>
      </section>

      <section className="panel">
        <h2>Posições</h2>
        <div className="table-scroll compact-scroll">
          <table className="table dense-table">
            <thead>
              <tr>
                <th>Símbolo</th>
                <th>Quantidade</th>
                <th>Custo médio</th>
                <th>Preço atual</th>
                <th>Valor de mercado</th>
                <th>P&amp;L não realizado</th>
                <th>P&amp;L realizado</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {positions.length === 0 ? (
                <tr>
                  <td colSpan={8} className="muted">
                    Nenhuma transação registrada ainda.
                  </td>
                </tr>
              ) : (
                positions.map((p) => (
                  <tr key={p.symbol}>
                    <td>
                      <a
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          showHistory(p.symbol);
                        }}
                      >
                        {p.symbol}
                      </a>
                    </td>
                    <td>{fmt(p.quantity, 4)}</td>
                    <td>{fmt(p.avg_cost)}</td>
                    <td>{fmt(p.current_price)}</td>
                    <td>{fmt(p.market_value)}</td>
                    <td className={(p.unrealized_pnl ?? 0) >= 0 ? 'up' : 'down'}>{fmt(p.unrealized_pnl)}</td>
                    <td className={p.realized_pnl >= 0 ? 'up' : 'down'}>{fmt(p.realized_pnl)}</td>
                    <td>
                      <a
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          showHistory(p.symbol);
                        }}
                      >
                        histórico
                      </a>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {historySymbol && (
        <section className="panel">
          <h2>Histórico — {historySymbol}</h2>
          <div className="table-scroll compact-scroll">
            <table className="table dense-table">
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Lado</th>
                  <th>Quantidade</th>
                  <th>Preço</th>
                  <th>Nota</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {history.map((t) => (
                  <tr key={t.id}>
                    <td>{new Date(t.executed_at).toLocaleString('pt-BR')}</td>
                    <td>{t.side === 'BUY' ? 'Compra' : 'Venda'}</td>
                    <td>{fmt(t.quantity, 4)}</td>
                    <td>{fmt(t.price)}</td>
                    <td className="muted">{t.notes}</td>
                    <td>
                      <button type="button" className="link-btn danger" onClick={() => handleDeleteTransaction(t.id)}>
                        remover
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
