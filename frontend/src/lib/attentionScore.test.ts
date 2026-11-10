import { describe, expect, it } from 'vitest';
import { attentionScore } from './attentionScore';

const now = new Date('2026-09-23T15:00:00Z');
const base = { symbol: 'NVDA', price: 180, changePct: 0, takenAt: '2026-09-23T14:58:00Z', newsCount: 0, alertCount: 0, hasEarnings: false, now };

describe('attentionScore', () => {
  it('parte de 50 sem sinais', () => {
    const r = attentionScore(base);
    expect(r.total).toBe(50);
    expect(r.level).toBe('baixa');
  });

  it('reproduz o cálculo antigo do Dashboard', () => {
    // 50 + 2*3 + min(12, 3*3) + min(12, 2*4) = 50 + 6 + 9 + 8 = 73
    const r = attentionScore({ ...base, changePct: 2, newsCount: 3, alertCount: 2 });
    expect(r.total).toBe(73);
    expect(r.level).toBe('media');
  });

  it('limita o movimento a ±18 e as contagens a 12', () => {
    const r = attentionScore({ ...base, changePct: 10, newsCount: 10, alertCount: 10 });
    expect(r.components.find((c) => c.key === 'movimento')!.value).toBe(18);
    expect(r.components.find((c) => c.key === 'noticias')!.value).toBe(12);
    expect(r.components.find((c) => c.key === 'alertas')!.value).toBe(12);
    expect(r.total).toBe(92);
    expect(r.level).toBe('alta');
  });

  it('penaliza earnings e dado ausente ou atrasado', () => {
    expect(attentionScore({ ...base, hasEarnings: true }).total).toBe(42);
    expect(attentionScore({ ...base, price: null, takenAt: null }).total).toBe(25);
    expect(attentionScore({ ...base, takenAt: '2026-09-23T14:00:00Z' }).total).toBe(40);
  });

  it('a soma dos componentes explica o total', () => {
    const r = attentionScore({ ...base, changePct: -1.5, newsCount: 1, alertCount: 1, hasEarnings: true });
    const sum = 50 + r.components.reduce((s, c) => s + c.value, 0);
    expect(r.total).toBe(Math.round(sum));
  });

  it('mantém o total entre 0 e 100', () => {
    const r = attentionScore({ ...base, changePct: -20, price: null, takenAt: null, hasEarnings: true });
    expect(r.total).toBe(0);
  });
});
