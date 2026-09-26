import { api } from '../api/client';
import type { WatchlistItem } from '../types';

export const SYMBOL_RE = /^[A-Z0-9.^=/-]{1,15}$/;

export function normalizeSymbol(raw: string): string {
  return raw.trim().toUpperCase();
}

/** Adiciona à watchlist; o backend infere o tipo do ativo quando `asset_type` vem vazio. */
export function addToWatchlist(symbol: string, label = ''): Promise<WatchlistItem> {
  return api.post<WatchlistItem>('/api/watchlist', { symbol: normalizeSymbol(symbol), label, asset_type: '' });
}

export function createAlertHref(symbol: string): string {
  return `/watchlist?regra=${encodeURIComponent(normalizeSymbol(symbol))}`;
}

export function analyzeHref(symbol: string): string {
  return `/assistente?modo=ativo&symbol=${encodeURIComponent(normalizeSymbol(symbol))}`;
}

export function assetHref(symbol: string): string {
  return `/ativo/${encodeURIComponent(normalizeSymbol(symbol))}`;
}
