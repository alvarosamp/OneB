/**
 * Motor do Laboratório da Academia: conta simulada com compra no ask, venda no
 * bid, stop e alvo verificados barra a barra. Funções puras (sem React), para
 * testar e para usar igual no replay e no modo ao vivo.
 *
 * Regras conservadoras, as mesmas da pesquisa do OneB:
 * - se stop e alvo cabem na mesma barra, conta o stop (não sabemos a ordem);
 * - se a barra abre além do stop (gap), sai no preço de abertura, não no stop.
 */

export type Side = 'BUY' | 'SELL';
export type ExitReason = 'STOP' | 'TARGET' | 'MANUAL';

export interface LabBar {
  t: number;
  o: number;
  h: number;
  l: number;
  c: number;
}

export interface LabPosition {
  id: number;
  side: Side;
  units: number;
  entry: number;
  stop: number | null;
  target: number | null;
  openedAt: number;
}

export interface LabTrade extends LabPosition {
  exit: number;
  closedAt: number;
  pnl: number;
  /** Resultado em múltiplos do risco inicial; null quando a posição não tinha stop. */
  r: number | null;
  reason: ExitReason;
}

export interface LabState {
  balance: number;
  positions: LabPosition[];
  trades: LabTrade[];
  nextId: number;
}

export interface OrderInput {
  side: Side;
  units: number;
  stop: number | null;
  target: number | null;
}

export function initLab(balance = 10_000): LabState {
  return { balance, positions: [], trades: [], nextId: 1 };
}

export function quote(mid: number, spread: number): { bid: number; ask: number } {
  return { bid: mid - spread / 2, ask: mid + spread / 2 };
}

/** Quantidade para arriscar riskPct% do saldo até o stop (arredonda para baixo, 2 casas). */
export function sizeByRisk(balance: number, riskPct: number, entry: number, stop: number): number {
  const unitRisk = Math.abs(entry - stop);
  if (!(unitRisk > 0) || !(balance > 0) || !(riskPct > 0)) return 0;
  return Math.floor(((balance * riskPct) / 100 / unitRisk) * 100) / 100;
}

/** Erro em português se a ordem não fizer sentido; null se estiver ok. */
export function validateOrder(o: OrderInput, fill: number): string | null {
  if (!(o.units > 0)) return 'Informe uma quantidade maior que zero.';
  if (o.side === 'BUY') {
    if (o.stop !== null && o.stop >= fill) return 'Na compra, o stop fica abaixo do preço de entrada.';
    if (o.target !== null && o.target <= fill) return 'Na compra, o alvo fica acima do preço de entrada.';
  } else {
    if (o.stop !== null && o.stop <= fill) return 'Na venda, o stop fica acima do preço de entrada.';
    if (o.target !== null && o.target >= fill) return 'Na venda, o alvo fica abaixo do preço de entrada.';
  }
  return null;
}

export function openPosition(state: LabState, o: OrderInput, mid: number, spread: number, at: number): { state: LabState; error: string | null } {
  const { bid, ask } = quote(mid, spread);
  const fill = o.side === 'BUY' ? ask : bid;
  const error = validateOrder(o, fill);
  if (error) return { state, error };
  const position: LabPosition = { id: state.nextId, side: o.side, units: o.units, entry: fill, stop: o.stop, target: o.target, openedAt: at };
  return { state: { ...state, positions: [...state.positions, position], nextId: state.nextId + 1 }, error: null };
}

function settle(p: LabPosition, exit: number, at: number, reason: ExitReason): LabTrade {
  const dir = p.side === 'BUY' ? 1 : -1;
  const pnl = (exit - p.entry) * dir * p.units;
  const risk = p.stop === null ? null : Math.abs(p.entry - p.stop) * p.units;
  return { ...p, exit, closedAt: at, pnl, r: risk ? pnl / risk : null, reason };
}

/** Exit de uma posição dentro da barra, ou null. Compra sai no bid; venda sai no ask. */
export function exitInBar(p: LabPosition, bar: LabBar, spread: number): { price: number; reason: ExitReason } | null {
  const half = spread / 2;
  if (p.side === 'BUY') {
    const open = bar.o - half;
    const low = bar.l - half;
    const high = bar.h - half;
    if (p.stop !== null && open <= p.stop) return { price: open, reason: 'STOP' };
    if (p.target !== null && open >= p.target) return { price: open, reason: 'TARGET' };
    if (p.stop !== null && low <= p.stop) return { price: p.stop, reason: 'STOP' };
    if (p.target !== null && high >= p.target) return { price: p.target, reason: 'TARGET' };
  } else {
    const open = bar.o + half;
    const low = bar.l + half;
    const high = bar.h + half;
    if (p.stop !== null && open >= p.stop) return { price: open, reason: 'STOP' };
    if (p.target !== null && open <= p.target) return { price: open, reason: 'TARGET' };
    if (p.stop !== null && high >= p.stop) return { price: p.stop, reason: 'STOP' };
    if (p.target !== null && low <= p.target) return { price: p.target, reason: 'TARGET' };
  }
  return null;
}

/** Aplica uma barra nova: fecha posições cujo stop ou alvo foi atingido. */
export function onBar(state: LabState, bar: LabBar, spread: number): LabState {
  const open: LabPosition[] = [];
  const closed: LabTrade[] = [];
  for (const p of state.positions) {
    if (bar.t <= p.openedAt) {
      open.push(p); // a barra em que entrou não decide a saída (entrou no fechamento dela)
      continue;
    }
    const hit = exitInBar(p, bar, spread);
    if (hit) closed.push(settle(p, hit.price, bar.t, hit.reason));
    else open.push(p);
  }
  if (!closed.length) return state;
  return { ...state, positions: open, trades: [...state.trades, ...closed], balance: state.balance + closed.reduce((s, t) => s + t.pnl, 0) };
}

export function closePosition(state: LabState, id: number, mid: number, spread: number, at: number): LabState {
  const p = state.positions.find((x) => x.id === id);
  if (!p) return state;
  const { bid, ask } = quote(mid, spread);
  const trade = settle(p, p.side === 'BUY' ? bid : ask, at, 'MANUAL');
  return { ...state, positions: state.positions.filter((x) => x.id !== id), trades: [...state.trades, trade], balance: state.balance + trade.pnl };
}

export function openPnl(p: LabPosition, mid: number, spread: number): number {
  const { bid, ask } = quote(mid, spread);
  return p.side === 'BUY' ? (bid - p.entry) * p.units : (p.entry - ask) * p.units;
}

export function equity(state: LabState, mid: number | null, spread: number): number {
  if (mid === null) return state.balance;
  return state.balance + state.positions.reduce((s, p) => s + openPnl(p, mid, spread), 0);
}

export interface LabStats {
  count: number;
  winRate: number | null;
  expectancyR: number | null;
  avgWinR: number | null;
  avgLossR: number | null;
  totalPnl: number;
}

/** Placar do aluno: acerto E expectativa em R (a lição "acerto não é lucro"). */
export function labStats(trades: LabTrade[]): LabStats {
  const withR = trades.filter((t) => t.r !== null).map((t) => t.r as number);
  const wins = withR.filter((r) => r > 0);
  const losses = withR.filter((r) => r <= 0);
  const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
  return {
    count: trades.length,
    winRate: trades.length ? trades.filter((t) => t.pnl > 0).length / trades.length : null,
    expectancyR: mean(withR),
    avgWinR: mean(wins),
    avgLossR: mean(losses),
    totalPnl: trades.reduce((s, t) => s + t.pnl, 0),
  };
}
