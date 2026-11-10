import type { NavItem } from '../content/navigation';
import type { WatchlistItem } from '../types';
import { SYMBOL_RE } from './watchlist';

export type PaletteEntry =
  | { kind: 'asset'; id: string; symbol: string; label: string; inWatchlist: boolean }
  | { kind: 'page'; id: string; to: string; label: string };

export type AssetAction = 'chart' | 'watchlist' | 'alert' | 'analyze';

export const ASSET_ACTIONS: { id: AssetAction; label: string }[] = [
  { id: 'chart', label: 'Abrir gráfico' },
  { id: 'analyze', label: 'Analisar no Assistente' },
  { id: 'alert', label: 'Criar alerta' },
  { id: 'watchlist', label: 'Adicionar à watchlist' },
];

function norm(s: string) {
  return s
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();
}

/**
 * Resultados da busca: ativos da watchlist, o símbolo digitado (se válido e
 * fora da watchlist) e páginas. Sem endpoint de busca de símbolos na API,
 * qualquer ticker válido pode ser aberto diretamente.
 */
export function searchPalette(query: string, watchlist: WatchlistItem[], pages: NavItem[], limit = 8): PaletteEntry[] {
  const q = norm(query.trim());
  const upper = query.trim().toUpperCase();

  const assets = watchlist
    .filter((w) => !q || norm(w.symbol).includes(q) || norm(w.label ?? '').includes(q))
    .sort((a, b) => {
      const as = norm(a.symbol).startsWith(q) ? 0 : 1;
      const bs = norm(b.symbol).startsWith(q) ? 0 : 1;
      return as - bs || a.symbol.localeCompare(b.symbol);
    })
    .slice(0, q ? limit : 5)
    .map<PaletteEntry>((w) => ({ kind: 'asset', id: `asset:${w.symbol}`, symbol: w.symbol, label: w.label || w.symbol, inWatchlist: true }));

  const typed: PaletteEntry[] =
    upper && SYMBOL_RE.test(upper) && !watchlist.some((w) => w.symbol === upper)
      ? [{ kind: 'asset', id: `asset:${upper}`, symbol: upper, label: 'fora da watchlist', inWatchlist: false }]
      : [];

  const pageHits = pages
    .filter((p) => !q || [p.label, ...(p.keywords ?? [])].some((k) => norm(k).split(/[\s&/-]+/).some((w) => w.startsWith(q)) || norm(k).startsWith(q)))
    .map<PaletteEntry>((p) => ({ kind: 'page', id: `page:${p.to}`, to: p.to, label: p.label }));

  return [...assets, ...typed, ...pageHits];
}

export function actionsFor(entry: Extract<PaletteEntry, { kind: 'asset' }>) {
  return ASSET_ACTIONS.filter((a) => a.id !== 'watchlist' || !entry.inWatchlist);
}
