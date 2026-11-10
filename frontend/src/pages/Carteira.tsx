import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Trash2 } from 'lucide-react';
import { api } from '../api/client';
import { useApi } from '../hooks/useApi';
import { useToast } from '../context/ToastContext';
import { useConfirm } from '../components/ConfirmModal';
import { TabbedPage } from '../components/terminal/TabbedPage';
import { AsyncContent, Badge, Button, EmptyState, ICON, Input, Section, Select, SkeletonLines, Stat, Table, Textarea, type Column } from '../components/ui';
import { formatCurrency, formatDateTime, formatNumber, formatSignedCurrency, formatSignedPct, isNum } from '../lib/format';
import { ptBR } from '../lib/text';
import { assetHref, normalizeSymbol, SYMBOL_RE } from '../lib/watchlist';
import type { DecisionJournal, PositionSummary, TraderProfile, TraderProfileGroup, Transaction, TransactionSide } from '../types';
import styles from './Carteira.module.css';

type Tab = 'posicoes' | 'operacoes' | 'desempenho';

/** Carteira: posições e P&L, operações lançadas e diário, desempenho do trader. */
export function Carteira() {
  return (
    <TabbedPage<Tab>
      title="Carteira"
      description="Lançamento manual das suas operações para acompanhar resultado. O OneB não se conecta a corretoras e não executa ordens."
      fallback="posicoes"
      tabs={[
        { value: 'posicoes', label: 'Posições', render: () => <Positions /> },
        { value: 'operacoes', label: 'Operações', render: () => <Operations /> },
        { value: 'desempenho', label: 'Desempenho', render: () => <Performance /> },
      ]}
    />
  );
}

function pnlClass(v: number | null | undefined) {
  return !isNum(v) || v === 0 ? 'num' : v > 0 ? 'num up' : 'num down';
}

function Positions() {
  const positions = useApi<PositionSummary[]>('/api/positions', { pollMs: 60_000 });
  const rows = positions.data ?? [];
  const value = rows.reduce((s, p) => s + (p.market_value ?? 0), 0);
  const unrealized = rows.reduce((s, p) => s + (p.unrealized_pnl ?? 0), 0);
  const realized = rows.reduce((s, p) => s + (p.realized_pnl ?? 0), 0);
  const columns: Column<PositionSummary>[] = [
    { key: 'ativo', header: 'Ativo', sortValue: (p) => p.symbol, render: (p) => <Link to={assetHref(p.symbol)}><strong>{p.symbol}</strong></Link> },
    { key: 'qtd', header: 'Quantidade', align: 'right', sortValue: (p) => p.quantity, render: (p) => <span className="num">{formatNumber(p.quantity, p.quantity % 1 ? 4 : 0)}</span> },
    { key: 'custo', header: 'Custo médio', align: 'right', render: (p) => <span className="num">{formatCurrency(p.avg_cost)}</span> },
    { key: 'preco', header: 'Preço atual', align: 'right', render: (p) => <span className="num">{formatCurrency(p.current_price)}</span> },
    { key: 'valor', header: 'Valor de mercado', align: 'right', sortValue: (p) => p.market_value, render: (p) => <span className="num">{formatCurrency(p.market_value)}</span> },
    { key: 'naorealizado', header: 'P&L não realizado', align: 'right', sortValue: (p) => p.unrealized_pnl, render: (p) => <span className={pnlClass(p.unrealized_pnl)}>{formatSignedCurrency(p.unrealized_pnl)}</span> },
    {
      key: 'pct',
      header: 'Retorno',
      align: 'right',
      render: (p) => {
        const pct = isNum(p.current_price) && p.avg_cost ? ((p.current_price - p.avg_cost) / p.avg_cost) * 100 : null;
        return <span className={pnlClass(pct)}>{formatSignedPct(pct)}</span>;
      },
    },
    { key: 'realizado', header: 'P&L realizado', align: 'right', render: (p) => <span className={pnlClass(p.realized_pnl)}>{formatSignedCurrency(p.realized_pnl)}</span> },
  ];
  return (
    <div className={styles.stack}>
      <AsyncContent
        state={positions}
        loading={<SkeletonLines lines={6} />}
        empty={<EmptyState title="Nenhuma posição registrada" description="Registre suas compras e vendas na aba Operações para acompanhar o P&L." />}
        errorTitle="Não foi possível carregar as posições"
      >
        {() => (
          <>
            <div className={styles.stats}>
              <Stat label="Valor de mercado" value={formatCurrency(value)} size="lg" />
              <Stat label="P&L não realizado" value={<span className={pnlClass(unrealized)}>{formatSignedCurrency(unrealized)}</span>} size="lg" />
              <Stat label="P&L realizado" value={<span className={pnlClass(realized)}>{formatSignedCurrency(realized)}</span>} size="lg" />
            </div>
            <Table caption="Posições" columns={columns} rows={rows} rowKey={(p) => p.symbol} initialSort={{ key: 'valor', dir: 'desc' }} stickyFirstColumn />
          </>
        )}
      </AsyncContent>
    </div>
  );
}

function Operations() {
  const toast = useToast();
  const confirm = useConfirm();
  const positions = useApi<PositionSummary[]>('/api/positions');
  const [symbol, setSymbol] = useState('');
  const [side, setSide] = useState<TransactionSide>('BUY');
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [executedAt, setExecutedAt] = useState(() => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16));
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [historySymbol, setHistorySymbol] = useState('');
  const history = useApi<Transaction[]>(historySymbol ? `/api/positions/${encodeURIComponent(historySymbol)}/transactions` : null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const s = normalizeSymbol(symbol);
    if (!SYMBOL_RE.test(s)) return setError('Informe um símbolo válido.');
    if (!(Number(quantity) > 0) || !(Number(price) > 0)) return setError('Quantidade e preço precisam ser maiores que zero.');
    setError(null);
    setSaving(true);
    try {
      await api.post('/api/positions/transactions', { symbol: s, side, quantity: Number(quantity), price: Number(price), executed_at: new Date(executedAt).toISOString(), notes });
      toast(`Operação registrada em ${s}`, 'success');
      setQuantity('');
      setPrice('');
      setNotes('');
      positions.retry();
      if (historySymbol === s) history.retry();
      else setHistorySymbol(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível registrar a operação');
    } finally {
      setSaving(false);
    }
  }

  async function remove(t: Transaction) {
    if (!(await confirm(`Remover a operação de ${t.symbol} de ${formatDateTime(t.executed_at)}?`))) return;
    try {
      await api.delete(`/api/positions/transactions/${t.id}`);
      history.mutate((prev) => (prev ?? []).filter((x) => x.id !== t.id));
      positions.retry();
      toast('Operação removida', 'success');
    } catch (err) {
      toast(err instanceof Error ? `Não foi possível remover: ${err.message}` : 'Não foi possível remover', 'error');
    }
  }

  const columns: Column<Transaction>[] = [
    { key: 'data', header: 'Data', sortValue: (t) => t.executed_at, render: (t) => <span className="num">{formatDateTime(t.executed_at)}</span> },
    { key: 'lado', header: 'Lado', render: (t) => <Badge tone={t.side === 'BUY' ? 'info' : 'neutral'}>{t.side === 'BUY' ? 'Compra' : 'Venda'}</Badge> },
    { key: 'qtd', header: 'Quantidade', align: 'right', render: (t) => <span className="num">{formatNumber(t.quantity, t.quantity % 1 ? 4 : 0)}</span> },
    { key: 'preco', header: 'Preço', align: 'right', render: (t) => <span className="num">{formatCurrency(t.price)}</span> },
    { key: 'total', header: 'Total', align: 'right', render: (t) => <span className="num">{formatCurrency(t.price * t.quantity)}</span> },
    { key: 'nota', header: 'Nota', wrap: true, render: (t) => <span className="muted">{t.notes || '—'}</span> },
    { key: 'x', header: <span className="sr-only">Ações</span>, align: 'right', render: (t) => <Button size="sm" variant="ghost" iconOnly icon={<Trash2 {...ICON} />} aria-label="Remover operação" onClick={() => remove(t)} /> },
  ];

  const symbols = Array.from(new Set((positions.data ?? []).map((p) => p.symbol))).sort();

  return (
    <div className={styles.stack}>
      <Section title="Registrar operação">
        <form className={styles.form} onSubmit={submit}>
          <Input label="Ativo" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} placeholder="NVDA" className={styles.w140} />
          <Select label="Lado" value={side} onChange={(e) => setSide(e.target.value as TransactionSide)} className={styles.w140}>
            <option value="BUY">Compra</option>
            <option value="SELL">Venda</option>
          </Select>
          <Input label="Quantidade" type="number" step="0.0001" min="0" value={quantity} onChange={(e) => setQuantity(e.target.value)} className={styles.w140} />
          <Input label="Preço (US$)" type="number" step="0.01" min="0" value={price} onChange={(e) => setPrice(e.target.value)} className={styles.w140} />
          <Input label="Data e hora" type="datetime-local" value={executedAt} onChange={(e) => setExecutedAt(e.target.value)} className={styles.w220} />
          <Input label="Nota (opcional)" value={notes} onChange={(e) => setNotes(e.target.value)} className={styles.grow} />
          <Button type="submit" variant="primary" loading={saving}>
            Registrar operação
          </Button>
        </form>
        {error && <p className={styles.error}>{error}</p>}
      </Section>

      <Section
        title="Histórico por ativo"
        actions={
          <Select label="Ativo do histórico" hideLabel value={historySymbol} onChange={(e) => setHistorySymbol(e.target.value)} className={styles.w220}>
            <option value="">Escolha um ativo</option>
            {symbols.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </Select>
        }
      >
        {historySymbol ? (
          <AsyncContent state={history} empty={<EmptyState title={`Nenhuma operação de ${historySymbol}`} description="Registre uma operação acima." />}>
            {(list) => <Table caption={`Operações de ${historySymbol}`} columns={columns} rows={list} rowKey={(t) => t.id} initialSort={{ key: 'data', dir: 'desc' }} dense />}
          </AsyncContent>
        ) : (
          <p className="muted">Escolha um ativo para ver as operações lançadas. A API lista operações por ativo.</p>
        )}
      </Section>

      <DecisionDiary />
    </div>
  );
}

const DECISION_STATUS: Record<string, string> = { OPEN: 'Aberta', WATCHING: 'Em observação', CLOSED: 'Encerrada', INVALIDATED: 'Invalidada' };

function DecisionDiary() {
  const toast = useToast();
  const decisions = useApi<DecisionJournal[]>('/api/intelligence/decisions');
  const [form, setForm] = useState({ symbol: '', thesis: '', trigger: '', invalidation: '', timeframe: '', risk_notes: '' });
  const [saving, setSaving] = useState(false);
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!form.symbol.trim() || !form.thesis.trim()) return;
    setSaving(true);
    try {
      const d = await api.post<DecisionJournal>('/api/intelligence/decisions', { ...form, symbol: normalizeSymbol(form.symbol) });
      decisions.mutate((prev) => [d, ...(prev ?? [])]);
      setForm({ symbol: '', thesis: '', trigger: '', invalidation: '', timeframe: '', risk_notes: '' });
      toast('Decisão registrada no diário', 'success');
    } catch (err) {
      toast(err instanceof Error ? `Não foi possível registrar: ${err.message}` : 'Não foi possível registrar', 'error');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Section title="Diário de decisão" divided>
      <p className="muted">Escreva a tese, o gatilho e a invalidação antes de agir. Decisões de esperar também contam.</p>
      <form className={styles.diaryForm} onSubmit={submit}>
        <Input label="Ativo" value={form.symbol} onChange={set('symbol')} placeholder="NVDA" required />
        <Input label="Prazo" value={form.timeframe} onChange={set('timeframe')} placeholder="5 a 20 pregões" />
        <Textarea label="Tese" value={form.thesis} onChange={set('thesis')} rows={2} required className={styles.full} />
        <Input label="Gatilho" value={form.trigger} onChange={set('trigger')} placeholder="Rompimento de 180 com volume acima da média" />
        <Input label="Invalidação" value={form.invalidation} onChange={set('invalidation')} placeholder="Fechamento abaixo da EMA 20" />
        <Input label="Risco" value={form.risk_notes} onChange={set('risk_notes')} placeholder="1% do capital" className={styles.full} />
        <div>
          <Button type="submit" variant="primary" loading={saving}>
            Registrar decisão
          </Button>
        </div>
      </form>
      <AsyncContent state={decisions} empty={<p className="muted">Nenhuma decisão registrada ainda.</p>}>
        {(list) => (
          <ul className={styles.diary}>
            {list.map((d) => (
              <li key={d.id}>
                <span className={styles.diaryHead}>
                  <strong>{d.symbol}</strong>
                  <Badge>{DECISION_STATUS[d.status] ?? ptBR(d.status)}</Badge>
                  <span className="muted num">{formatDateTime(d.created_at)}</span>
                </span>
                <span>{d.thesis}</span>
                {(d.trigger || d.invalidation) && (
                  <span className="muted">
                    {d.trigger && <>Gatilho: {d.trigger}. </>}
                    {d.invalidation && <>Invalidação: {d.invalidation}.</>}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </AsyncContent>
    </Section>
  );
}

function Performance() {
  const profile = useApi<TraderProfile>('/api/profile/trader', { isEmpty: (p) => p.summary.transactions === 0 });
  const groupColumns: Column<TraderProfileGroup>[] = [
    { key: 'grupo', header: 'Grupo', render: (g) => ptBR(g.key) },
    { key: 'trades', header: 'Trades', align: 'right', sortValue: (g) => g.trades, render: (g) => <span className="num">{g.trades}</span> },
    { key: 'pnl', header: 'P&L', align: 'right', sortValue: (g) => g.pnl, render: (g) => <span className={pnlClass(g.pnl)}>{formatSignedCurrency(g.pnl)}</span> },
    { key: 'acerto', header: 'Acerto', align: 'right', render: (g) => <span className="num">{formatNumber(g.win_rate, 1)}%</span> },
    { key: 'ret', header: 'Retorno médio', align: 'right', render: (g) => <span className={pnlClass(g.avg_return_pct)}>{formatSignedPct(g.avg_return_pct)}</span> },
  ];
  return (
    <AsyncContent
      state={profile}
      loading={<SkeletonLines lines={8} />}
      empty={<EmptyState title="Sem operações para analisar" description="Registre operações na aba Operações. O diagnóstico usa as operações fechadas." />}
      errorTitle="Não foi possível calcular o desempenho"
    >
      {(p) => {
        const s = p.summary;
        return (
          <div className={styles.stack}>
            <div className={styles.stats}>
              <Stat label="P&L fechado" value={<span className={pnlClass(s.total_pnl)}>{formatSignedCurrency(s.total_pnl)}</span>} sub={`${s.closed_trades} trades fechados`} size="lg" />
              <Stat label="Taxa de acerto" value={`${formatNumber(s.win_rate, 1)}%`} sub={`${s.transactions} lançamentos`} size="lg" />
              <Stat label="Expectativa por trade" value={<span className={pnlClass(s.expectancy)}>{formatSignedCurrency(s.expectancy)}</span>} size="lg" />
              <Stat label="Profit factor" value={s.profit_factor === 999 ? 'sem perdas' : formatNumber(s.profit_factor, 2)} sub={`${formatNumber(s.avg_holding_hours, 1)} h em posição, em média`} size="lg" />
            </div>
            <div className={styles.two}>
              <Section title="Diagnóstico">
                {p.insights.length ? (
                  <ul className={styles.list}>
                    {p.insights.map((i) => (
                      <li key={i}>{ptBR(i)}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted">Ainda não há operações fechadas suficientes para um diagnóstico confiável.</p>
                )}
              </Section>
              <Section title="Resumo">
                <dl className={styles.dl}>
                  <dt>Ganho médio</dt>
                  <dd className="num">{formatCurrency(s.avg_win)}</dd>
                  <dt>Perda média</dt>
                  <dd className="num">{formatCurrency(s.avg_loss)}</dd>
                  <dt>Ativos com histórico</dt>
                  <dd>{s.open_symbols.length ? s.open_symbols.join(', ') : 'nenhum'}</dd>
                </dl>
              </Section>
            </div>
            <div className={styles.two}>
              <Section title="Por ativo">
                <Table caption="Desempenho por ativo" columns={groupColumns} rows={p.by_symbol} rowKey={(g) => g.key} dense empty={<p className="muted">Nenhum trade fechado.</p>} />
              </Section>
              <Section title="Por horário de entrada">
                <Table caption="Desempenho por horário" columns={groupColumns} rows={p.by_hour} rowKey={(g) => g.key} dense empty={<p className="muted">Nenhum horário analisável.</p>} />
              </Section>
            </div>
            <Section title="Por estilo">
              <Table caption="Desempenho por estilo" columns={groupColumns} rows={p.by_style} rowKey={(g) => g.key} dense empty={<p className="muted">Nenhum estilo identificado.</p>} />
            </Section>
            {p.journal.length > 0 && (
              <Section title="Trades fechados e lições">
                <ul className={styles.diary}>
                  {p.journal.map((j) => (
                    <li key={`${j.symbol}-${j.exit_at}`}>
                      <span className={styles.diaryHead}>
                        <strong>{j.symbol}</strong>
                        <span className={pnlClass(j.pnl)}>{formatSignedCurrency(j.pnl)}</span>
                        <span className={pnlClass(j.return_pct)}>{formatSignedPct(j.return_pct)}</span>
                        <span className="muted num">
                          {formatDateTime(j.entry_at)} a {formatDateTime(j.exit_at)}
                        </span>
                      </span>
                      <span className="muted">{ptBR(j.lesson)}</span>
                    </li>
                  ))}
                </ul>
              </Section>
            )}
          </div>
        );
      }}
    </AsyncContent>
  );
}
