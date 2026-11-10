/** Indicadores calculados no cliente a partir das barras da API (funções puras). */

export function ema(values: (number | null)[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  const k = 2 / (period + 1);
  let prev: number | null = null;
  let seedSum = 0;
  let seedCount = 0;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (v === null || !Number.isFinite(v)) {
      out[i] = prev;
      continue;
    }
    if (prev === null) {
      seedSum += v;
      seedCount++;
      if (seedCount === period) {
        prev = seedSum / period;
        out[i] = prev;
      }
      continue;
    }
    prev = v * k + prev * (1 - k);
    out[i] = prev;
  }
  return out;
}

export interface Bar {
  t: number;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
}

/**
 * VWAP intradiário, reiniciado a cada sessão (`sessionKey` devolve a data da sessão).
 * Retorna null onde não há volume.
 */
export function vwap(bars: Bar[], sessionKey: (t: number) => string): (number | null)[] {
  const out: (number | null)[] = [];
  let key = '';
  let pv = 0;
  let vol = 0;
  for (const b of bars) {
    const k = sessionKey(b.t);
    if (k !== key) {
      key = k;
      pv = 0;
      vol = 0;
    }
    const typical = (b.h + b.l + b.c) / 3;
    pv += typical * b.v;
    vol += b.v;
    out.push(vol > 0 ? pv / vol : null);
  }
  return out;
}

/** ATR de Wilder. */
export function atr(bars: Bar[], period = 14): (number | null)[] {
  const out: (number | null)[] = [];
  let prevClose: number | null = null;
  let value: number | null = null;
  const trs: number[] = [];
  for (const b of bars) {
    const tr = prevClose === null ? b.h - b.l : Math.max(b.h - b.l, Math.abs(b.h - prevClose), Math.abs(b.l - prevClose));
    prevClose = b.c;
    if (value === null) {
      trs.push(tr);
      if (trs.length === period) value = trs.reduce((a, x) => a + x, 0) / period;
      out.push(value);
    } else {
      value = (value * (period - 1) + tr) / period;
      out.push(value);
    }
  }
  return out;
}

export function lastValue(values: (number | null | undefined)[]): number | null {
  for (let i = values.length - 1; i >= 0; i--) {
    const v = values[i];
    if (v !== null && v !== undefined && Number.isFinite(v)) return v;
  }
  return null;
}
