import { describe, expect, it } from 'vitest';
import { simulate } from './simulator';

describe('simulate', () => {
  it('calcula quantidade pelo risco e limita pelo capital', () => {
    const r = simulate({ direction: 'LONG', capital: 10000, riskPct: 1, entry: 100, stop: 98, target: 106 });
    expect(r.quantity).toBe(50);
    expect(r.plannedRisk).toBe(100);
    expect(r.rr).toBe(3);
    expect(r.checks.every((c) => c.ok)).toBe(true);
    const capped = simulate({ direction: 'LONG', capital: 1000, riskPct: 2, entry: 100, stop: 99.9, target: 101 });
    expect(capped.quantity).toBe(10);
  });

  it('valida estrutura para baixa', () => {
    expect(simulate({ direction: 'SHORT', capital: 10000, riskPct: 1, entry: 100, stop: 102, target: 95 }).validStructure).toBe(true);
    expect(simulate({ direction: 'SHORT', capital: 10000, riskPct: 1, entry: 100, stop: 98, target: 95 }).validStructure).toBe(false);
  });
});
