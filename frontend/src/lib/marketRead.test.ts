import { describe, expect, it } from 'vitest';
import { readMarket } from './marketRead';
import type { RegimeReport, TechnicalAnalysis } from '../types';

function regime(label: string, score = 30): RegimeReport {
  return {
    symbol: 'NASDAQ',
    local_regime: { label, score, factors: [{ name: 'trend', impact: 30, evidence: 'EMA20 acima da EMA50 (1 vs 2).' }] },
    macro_context: 'NEUTRO',
    cross_asset_relevance: [],
  };
}

function tech(bias: string, macd: 'good' | 'danger', rsi = 55): TechnicalAnalysis {
  return {
    bias,
    rsi,
    atr_pct: 1.1,
    volatility_label: 'Media',
    signals: [{ name: 'macd', label: '', state: macd, evidence: '' }],
  } as unknown as TechnicalAnalysis;
}

describe('readMarket', () => {
  it('sem dados, sem leitura', () => {
    expect(readMarket(null, null)).toBeNull();
  });

  it('direções opostas → Sem setup com aviso', () => {
    const r = readMarket(regime('BULL'), tech('BAIXISTA', 'danger'))!;
    expect(r.state).toBe('sem-setup');
    expect(r.bias).toBeNull();
    expect(r.evidences[0].tone).toBe('warning');
  });

  it('mesma direção → Observar', () => {
    const r = readMarket(regime('BULL'), tech('ALTISTA', 'danger'))!;
    expect(r.state).toBe('observar');
    expect(r.bias).toBe('alta');
  });

  it('regime forte + MACD alinhado → Setup em formação', () => {
    const r = readMarket(regime('STRONG BEAR', -70), tech('BAIXISTA', 'danger'))!;
    expect(r.state).toBe('formacao');
    expect(r.bias).toBe('baixa');
  });

  it('entrega de 2 a 4 evidências curtas', () => {
    const r = readMarket(regime('BULL'), tech('ALTISTA', 'good', 72))!;
    expect(r.evidences.length).toBeGreaterThanOrEqual(2);
    expect(r.evidences.length).toBeLessThanOrEqual(4);
    expect(r.evidences.some((e) => e.text.includes('esticado'))).toBe(true);
  });
});
