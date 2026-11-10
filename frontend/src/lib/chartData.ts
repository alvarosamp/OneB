import { ema, vwap, type Bar } from './indicators';
import { nySessionKey, windowStart, type Timeframe } from './timeframes';
import type { ChartData } from '../types';

export interface Prepared {
  bars: Bar[];
  ema20: (number | null)[];
  ema200: (number | null)[];
  vwap: (number | null)[] | null;
  rsi: (number | null)[];
  macd: (number | null)[];
  signal: (number | null)[];
  hasEma200: boolean;
}
/** Prepara barras e indicadores na série completa e recorta a janela visível. */
export function prepareChart(data: ChartData, tf: Timeframe): Prepared {
  const all: Bar[] = [];
  const idx: number[] = [];
  data.timestamps.forEach((ts, i) => {
    const o = data.open[i];
    const h = data.high[i];
    const l = data.low[i];
    const c = data.close[i];
    if (o === null || h === null || l === null || c === null) return;
    all.push({ t: new Date(ts).getTime(), o, h, l, c, v: data.volume[i] ?? 0 });
    idx.push(i);
  });
  const closes = all.map((b) => b.c);
  const e20 = ema(closes, 20);
  const e200 = ema(closes, 200);
  const hasVolume = all.some((b) => b.v > 0);
  const vw = tf.intraday && hasVolume ? vwap(all, nySessionKey) : null;
  const start = windowStart(
    all.map((b) => b.t),
    tf,
    nySessionKey,
  );
  const from = Math.max(0, all.findIndex((b) => b.t >= start));
  const pick = <T,>(arr: T[]) => arr.slice(from);
  const pickIdx = (arr: (number | null)[]) => idx.slice(from).map((i) => arr[i] ?? null);
  const ema200Visible = pick(e200);
  return {
    bars: pick(all),
    ema20: pick(e20),
    ema200: ema200Visible,
    vwap: vw ? pick(vw) : null,
    rsi: pickIdx(data.rsi),
    macd: pickIdx(data.macd),
    signal: pickIdx(data.macd_signal),
    hasEma200: ema200Visible.some((v) => v !== null),
  };
}
