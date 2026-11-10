import { describe, expect, it } from 'vitest';
import { prepareChart } from './chartData';
import { findTimeframe } from './timeframes';
import type { ChartData } from '../types';

function series(n: number, stepMs: number, start = Date.UTC(2026, 0, 5, 14, 30)): ChartData {
  const ts = Array.from({ length: n }, (_, i) => new Date(start + i * stepMs).toISOString());
  const c = ts.map((_, i) => 100 + i);
  return { symbol: 'X', timestamps: ts, open: c, high: c.map((v) => v + 1), low: c.map((v) => v - 1), close: c, volume: c.map(() => 10), rsi: c.map(() => 50), macd: c.map(() => 0), macd_signal: c.map(() => 0), ema_fast: c, ema_slow: c };
}

describe('prepareChart', () => {
  it('calcula EMA 200 na série inteira e recorta a janela', () => {
    const day = 24 * 3600 * 1000;
    const p = prepareChart(series(500, day), findTimeframe('6M'));
    expect(p.bars.length).toBeLessThan(500);
    expect(p.bars.length).toBeGreaterThan(150);
    expect(p.hasEma200).toBe(true);
    expect(p.vwap).toBeNull();
  });

  it('não mostra EMA 200 sem histórico suficiente e calcula VWAP no intradiário', () => {
    const p = prepareChart(series(60, 5 * 60 * 1000), findTimeframe('1D'));
    expect(p.hasEma200).toBe(false);
    expect(p.vwap).not.toBeNull();
  });

  it('ignora candles incompletos', () => {
    const d = series(30, 60_000);
    d.open[3] = null;
    const p = prepareChart(d, findTimeframe('1D'));
    expect(p.bars.some((b) => Number.isNaN(b.o))).toBe(false);
    expect(p.bars.length).toBe(29);
  });
});
