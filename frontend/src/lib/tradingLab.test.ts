import { describe, expect, it } from 'vitest';
import { closePosition, equity, exitInBar, initLab, labStats, onBar, openPosition, sizeByRisk, validateOrder } from './tradingLab';

const bar = (t: number, o: number, h: number, l: number, c: number) => ({ t, o, h, l, c });

describe('tradingLab', () => {
  it('compra no ask e vende no bid', () => {
    const buy = openPosition(initLab(), { side: 'BUY', units: 1, stop: 90, target: 120 }, 100, 2, 0);
    expect(buy.state.positions[0].entry).toBe(101);
    const sell = openPosition(initLab(), { side: 'SELL', units: 1, stop: 110, target: 80 }, 100, 2, 0);
    expect(sell.state.positions[0].entry).toBe(99);
  });

  it('recusa stop e alvo do lado errado', () => {
    expect(validateOrder({ side: 'BUY', units: 1, stop: 105, target: 120 }, 101)).toMatch(/stop fica abaixo/);
    expect(validateOrder({ side: 'SELL', units: 1, stop: 110, target: 90 }, 99)).toBeNull();
    expect(validateOrder({ side: 'SELL', units: 1, stop: 110, target: 105 }, 99)).toMatch(/alvo fica abaixo/);
    expect(validateOrder({ side: 'SELL', units: 0, stop: null, target: null }, 99)).toMatch(/quantidade/);
  });

  it('stop e alvo na mesma barra: conta o stop (conservador)', () => {
    const p = { id: 1, side: 'BUY' as const, units: 1, entry: 100, stop: 95, target: 110, openedAt: 0 };
    expect(exitInBar(p, bar(1, 100, 112, 94, 105), 0)).toEqual({ price: 95, reason: 'STOP' });
  });

  it('gap além do stop sai na abertura, não no stop', () => {
    const p = { id: 1, side: 'BUY' as const, units: 1, entry: 100, stop: 95, target: 110, openedAt: 0 };
    expect(exitInBar(p, bar(1, 90, 92, 88, 91), 0)).toEqual({ price: 90, reason: 'STOP' });
  });

  it('venda é avaliada pelo ask (spread conta contra)', () => {
    const p = { id: 1, side: 'SELL' as const, units: 1, entry: 100, stop: 104, target: 90, openedAt: 0 };
    // máxima 103 no mid + meio spread de 1,5 = 104,5 no ask: stop atingido
    expect(exitInBar(p, bar(1, 101, 103, 100, 102), 3)).toEqual({ price: 104, reason: 'STOP' });
  });

  it('fecha no alvo, atualiza saldo e calcula R', () => {
    let s = openPosition(initLab(1000), { side: 'BUY', units: 2, stop: 95, target: 110 }, 100, 0, 0).state;
    s = onBar(s, bar(0, 100, 120, 99, 110), 0); // barra da entrada não decide
    expect(s.positions).toHaveLength(1);
    s = onBar(s, bar(1, 101, 111, 100, 110), 0);
    expect(s.positions).toHaveLength(0);
    expect(s.trades[0]).toMatchObject({ reason: 'TARGET', exit: 110, pnl: 20, r: 2 });
    expect(s.balance).toBe(1020);
  });

  it('fechamento manual e patrimônio com posição aberta', () => {
    const s = openPosition(initLab(1000), { side: 'BUY', units: 1, stop: null, target: null }, 100, 2, 0).state;
    expect(equity(s, 110, 2)).toBe(1000 + (109 - 101));
    const closed = closePosition(s, 1, 110, 2, 5);
    expect(closed.trades[0]).toMatchObject({ reason: 'MANUAL', pnl: 8, r: null });
  });

  it('dimensiona pelo risco', () => {
    expect(sizeByRisk(10_000, 1, 100, 98)).toBe(50);
    expect(sizeByRisk(10_000, 1, 100, 100)).toBe(0);
  });

  it('placar mostra que acerto alto pode ter expectativa negativa', () => {
    const t = (r: number) => ({ id: 1, side: 'BUY' as const, units: 1, entry: 100, stop: 99, target: null, openedAt: 0, exit: 0, closedAt: 1, pnl: r, r, reason: 'MANUAL' as const });
    const st = labStats([t(0.3), t(0.3), t(0.3), t(0.3), t(0.3), t(0.3), t(0.3), t(-1), t(-1), t(-1)]);
    expect(st.winRate).toBeCloseTo(0.7);
    expect(st.expectancyR).toBeCloseTo(-0.09);
  });
});
