import { describe, expect, it } from 'vitest';
import { atr, ema, lastValue, vwap, type Bar } from './indicators';

describe('indicadores', () => {
  it('EMA começa após o período com a média simples', () => {
    const out = ema([1, 2, 3, 4, 5], 3);
    expect(out[0]).toBeNull();
    expect(out[1]).toBeNull();
    expect(out[2]).toBe(2);
    expect(out[3]).toBeCloseTo(3);
    expect(out[4]).toBeCloseTo(4);
  });

  it('EMA não quebra com buracos', () => {
    const out = ema([1, null, 3, 5], 2);
    expect(out[2]).toBe(2);
    expect(out[3]).toBeCloseTo(4);
  });

  it('VWAP reinicia a cada sessão', () => {
    const bars: Bar[] = [
      { t: 1, o: 10, h: 10, l: 10, c: 10, v: 100 },
      { t: 2, o: 20, h: 20, l: 20, c: 20, v: 100 },
      { t: 3, o: 30, h: 30, l: 30, c: 30, v: 50 },
    ];
    const out = vwap(bars, (t) => (t < 3 ? 'a' : 'b'));
    expect(out).toEqual([10, 15, 30]);
  });

  it('ATR usa média de Wilder', () => {
    const bars: Bar[] = Array.from({ length: 4 }, (_, i) => ({ t: i, o: 10, h: 11, l: 9, c: 10, v: 1 }));
    const out = atr(bars, 2);
    expect(out[0]).toBeNull();
    expect(out[1]).toBe(2);
    expect(out[3]).toBe(2);
  });

  it('lastValue ignora nulos no fim', () => {
    expect(lastValue([1, 2, null])).toBe(2);
    expect(lastValue([])).toBeNull();
  });
});
