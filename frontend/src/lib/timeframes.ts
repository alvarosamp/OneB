/**
 * Timeframes do gráfico. Os pares period/interval são os que o backend
 * (yfinance) aceita e que a Mesa técnica já usava. Cada preset busca um
 * período maior que o exibido para que a EMA 200 tenha histórico suficiente.
 */
export interface Timeframe {
  id: '1D' | '5D' | '1M' | '6M' | '1A';
  label: string;
  period: string;
  interval: string;
  /** Janela exibida em milissegundos. */
  windowMs: number;
  intraday: boolean;
}

const DAY = 24 * 60 * 60 * 1000;

export const TIMEFRAMES: Timeframe[] = [
  { id: '1D', label: '1D', period: '5d', interval: '5m', windowMs: 1 * DAY, intraday: true },
  { id: '5D', label: '5D', period: '1mo', interval: '15m', windowMs: 5 * DAY, intraday: true },
  { id: '1M', label: '1M', period: '3mo', interval: '1h', windowMs: 31 * DAY, intraday: true },
  { id: '6M', label: '6M', period: '2y', interval: '1d', windowMs: 183 * DAY, intraday: false },
  { id: '1A', label: '1A', period: '2y', interval: '1d', windowMs: 366 * DAY, intraday: false },
];

export function findTimeframe(id: string | null | undefined): Timeframe {
  return TIMEFRAMES.find((t) => t.id === id) ?? TIMEFRAMES[1];
}

export function chartPath(symbol: string, tf: Pick<Timeframe, 'period' | 'interval'>): string {
  return `/api/chart/${encodeURIComponent(symbol)}?period=${tf.period}&interval=${tf.interval}`;
}

/**
 * Início da janela visível. Para o 1D usa a última sessão com dados (não 24h
 * corridas), e para o 5D as últimas 5 sessões, para não abrir no fim de semana vazio.
 */
export function windowStart(timestamps: number[], tf: Timeframe, sessionKey: (t: number) => string): number {
  if (timestamps.length === 0) return 0;
  const last = timestamps[timestamps.length - 1];
  if (tf.id === '1D' || tf.id === '5D') {
    const sessions = tf.id === '1D' ? 1 : 5;
    const seen: string[] = [];
    for (let i = timestamps.length - 1; i >= 0; i--) {
      const k = sessionKey(timestamps[i]);
      if (!seen.includes(k)) {
        if (seen.length === sessions) return timestamps[i + 1];
        seen.push(k);
      }
    }
    return timestamps[0];
  }
  return last - tf.windowMs;
}

/** Data da sessão em Nova York (chave para VWAP e janelas). */
export function nySessionKey(t: number): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' }).format(t);
}
