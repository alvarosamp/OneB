import { describe, expect, it } from 'vitest';
import { LayoutDashboard } from 'lucide-react';
import { actionsFor, searchPalette } from './commandPalette';
import type { WatchlistItem } from '../types';

const wl = [
  { id: 1, symbol: 'NVDA', label: 'NVIDIA', asset_type: 'equity', active: true },
  { id: 2, symbol: 'AAPL', label: 'Apple', asset_type: 'equity', active: true },
] as WatchlistItem[];
const pages = [
  { to: '/ferramenta', label: 'Hoje', icon: LayoutDashboard },
  { to: '/analise', label: 'Análise', icon: LayoutDashboard, keywords: ['regime'] },
];

describe('searchPalette', () => {
  it('encontra ativos por símbolo e nome', () => {
    expect(searchPalette('nvd', wl, pages)[0]).toMatchObject({ kind: 'asset', symbol: 'NVDA' });
    expect(searchPalette('apple', wl, pages)[0]).toMatchObject({ symbol: 'AAPL' });
  });

  it('oferece o símbolo digitado quando não está na watchlist', () => {
    const r = searchPalette('msft', wl, pages);
    expect(r[0]).toMatchObject({ kind: 'asset', symbol: 'MSFT', inWatchlist: false });
  });

  it('busca páginas ignorando acentos e por palavra-chave', () => {
    expect(searchPalette('analise', wl, pages).some((e) => e.kind === 'page' && e.to === '/analise')).toBe(true);
    expect(searchPalette('regime', wl, pages).some((e) => e.kind === 'page' && e.to === '/analise')).toBe(true);
  });

  it('não sugere adicionar à watchlist o que já está nela', () => {
    const [nvda] = searchPalette('NVDA', wl, pages);
    if (nvda.kind !== 'asset') throw new Error('esperava ativo');
    expect(actionsFor(nvda).map((a) => a.id)).not.toContain('watchlist');
    const [msft] = searchPalette('MSFT', wl, pages);
    if (msft.kind !== 'asset') throw new Error('esperava ativo');
    expect(actionsFor(msft).map((a) => a.id)).toContain('watchlist');
  });
});
