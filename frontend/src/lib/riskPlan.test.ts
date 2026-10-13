import { describe, expect, it } from 'vitest';
import { riskPlan } from './riskPlan';
import { binOf, brasiliaOffset } from './heatmap';

describe('riskPlan', () => {
  it('ouro: 1% de 10.000 com stop de 10 dólares = 0,10 lote', () => {
    const p = riskPlan({ balance: 10_000, riskPct: 1, stopPoints: 10, contractSize: 100, volumeMin: 0.01, volumeStep: 0.01, spreadPoints: 0.26 })!;
    expect(p.riskMoney).toBe(100);
    expect(p.lots).toBeCloseTo(0.1);
    expect(p.spreadCost).toBeCloseTo(2.6);
  });

  it('arredonda para baixo: nunca arrisca mais que o pedido', () => {
    const p = riskPlan({ balance: 10_000, riskPct: 1, stopPoints: 30, contractSize: 1, volumeMin: 1, volumeStep: 1, spreadPoints: 0.7 })!;
    expect(p.lots).toBe(3); // 3,33 -> 3
    expect(p.actualRisk).toBeLessThanOrEqual(100);
  });

  it('lote mínimo grande demais para o risco vira zero e avisa', () => {
    const p = riskPlan({ balance: 500, riskPct: 1, stopPoints: 60, contractSize: 1, volumeMin: 1, volumeStep: 1, spreadPoints: 0.7 })!;
    expect(p.lots).toBe(0);
    expect(p.belowMinimum).toBe(true);
  });

  it('entrada inválida devolve null', () => {
    expect(riskPlan({ balance: 0, riskPct: 1, stopPoints: 10, contractSize: 1, volumeMin: 1, volumeStep: 1, spreadPoints: null })).toBeNull();
  });
});

describe('heatmap', () => {
  it('faixas de movimento', () => {
    expect(binOf('ratio', 0.3)).toBe(0);
    expect(binOf('ratio', 1)).toBe(2);
    expect(binOf('ratio', 5)).toBe(4);
  });

  it('Brasília fica 1 h à frente de NY no verão americano e 2 h no inverno', () => {
    expect(brasiliaOffset(new Date('2026-07-15T15:00:00Z'))).toBe(1);
    expect(brasiliaOffset(new Date('2026-01-15T15:00:00Z'))).toBe(2);
  });
});
