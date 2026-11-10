/** Formatação pt-BR para números, moeda, variação e idade do dado. */

export type Currency = 'USD' | 'BRL';

const LOCALE = 'pt-BR';

export function isNum(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (!isNum(value)) return '—';
  return value.toLocaleString(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** Moeda sempre explícita: "US$ 1.234,50" / "R$ 5,42". */
export function formatCurrency(value: number | null | undefined, currency: Currency = 'USD', digits = 2): string {
  if (!isNum(value)) return '—';
  const formatted = value.toLocaleString(LOCALE, {
    style: 'currency',
    currency,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  // Intl pode usar espaço estreito; normaliza para espaço comum.
  return formatted.replace(/ | /g, ' ');
}

export function formatSignedPct(value: number | null | undefined, digits = 2): string {
  if (!isNum(value)) return '—';
  const sign = value > 0 ? '+' : value < 0 ? '−' : '';
  return `${sign}${Math.abs(value).toLocaleString(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`;
}

export function formatSigned(value: number | null | undefined, digits = 2): string {
  if (!isNum(value)) return '—';
  const sign = value > 0 ? '+' : value < 0 ? '−' : '';
  return `${sign}${Math.abs(value).toLocaleString(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

export function formatSignedCurrency(value: number | null | undefined, currency: Currency = 'USD'): string {
  if (!isNum(value)) return '—';
  const sign = value > 0 ? '+' : value < 0 ? '−' : '';
  return `${sign}${formatCurrency(Math.abs(value), currency)}`;
}

/**
 * O backend grava em UTC, mas com SQLite devolve ISO sem fuso ("2026-09-23T19:08:53").
 * Sem correção, o navegador leria como hora local. Strings sem offset são tratadas como UTC.
 */
export function parseApiDate(input: string): Date {
  const naive = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(input);
  return new Date(naive ? `${input}Z` : input);
}

function toDate(input: string | number | Date | null | undefined): Date | null {
  if (input === null || input === undefined || input === '') return null;
  const d = input instanceof Date ? input : typeof input === 'string' ? parseApiDate(input) : new Date(input);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function minutesSince(input: string | number | Date | null | undefined, now: Date = new Date()): number | null {
  const d = toDate(input);
  if (!d) return null;
  return Math.max(0, Math.round((now.getTime() - d.getTime()) / 60000));
}

/** "agora", "há 3 min", "há 2 h", "há 3 dias". */
export function formatAge(input: string | number | Date | null | undefined, now: Date = new Date()): string {
  const minutes = minutesSince(input, now);
  if (minutes === null) return 'sem dado';
  if (minutes < 1) return 'agora';
  if (minutes < 60) return `há ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `há ${hours} h`;
  const days = Math.floor(hours / 24);
  return days === 1 ? 'há 1 dia' : `há ${days} dias`;
}

export function formatTime(input: string | Date | null | undefined): string {
  const d = toDate(input);
  if (!d) return '—';
  return d.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit' });
}

export function formatDate(input: string | Date | null | undefined): string {
  const d = toDate(input);
  if (!d) return '—';
  return d.toLocaleDateString(LOCALE, { day: '2-digit', month: '2-digit' });
}

export function formatDateTime(input: string | Date | null | undefined): string {
  const d = toDate(input);
  if (!d) return '—';
  return d.toLocaleString(LOCALE, { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

export function formatLongDate(input: string | Date | null | undefined): string {
  const d = toDate(input);
  if (!d) return '—';
  return d.toLocaleDateString(LOCALE, { weekday: 'short', day: '2-digit', month: 'short' });
}

/**
 * Moeda do ativo pelo sufixo do símbolo. Ativos da B3 (.SA) e pares BRL em R$;
 * o resto em US$ (o foco do OneB é NASDAQ/COMEX).
 */
export function currencyForSymbol(symbol: string): Currency {
  const s = symbol.toUpperCase();
  if (s.endsWith('.SA') || s === 'BRL=X' || s === 'USD/BRL' || s === 'USDBRL') return 'BRL';
  return 'USD';
}

/** Preço formatado conforme o tipo de instrumento (índices/yields sem moeda). */
export function formatPrice(value: number | null | undefined, symbol: string): string {
  const s = symbol.toUpperCase();
  if (['VIX', '^VIX', 'DXY', 'DX-Y.NYB'].includes(s)) return formatNumber(value, 2);
  if (['US2Y', 'US5Y', 'US10Y', 'US30Y', '^TNX'].includes(s)) return isNum(value) ? `${formatNumber(value, 2)}%` : '—';
  if (['NASDAQ', 'NQ=F', 'SP500', 'ES=F', '^NDX', '^GSPC'].includes(s)) return formatNumber(value, 2);
  return formatCurrency(value, currencyForSymbol(s));
}
