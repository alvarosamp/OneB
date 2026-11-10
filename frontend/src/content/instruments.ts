/**
 * Instrumentos do ticker do Hoje. Só entram os que a API fornece hoje:
 * /api/regime/macro (NASDAQ, GOLD, DXY, VIX, US10Y) e /api/fx/usd-brl.
 * `spark` é o símbolo Yahoo usado em /api/chart para a forma do movimento
 * (só quando a série é a mesma do preço exibido).
 */
export interface TickerInstrument {
  id: string;
  label: string;
  name: string;
  source: 'macro' | 'fx';
  macroKey?: string;
  spark: string | null;
  kind: 'index' | 'usd' | 'brl' | 'yield';
  href?: string;
  /** Minutos a partir dos quais o dado é "atrasado". Séries diárias do FRED toleram mais. */
  staleAfterMin: number;
  note?: string;
}

export const TICKER: TickerInstrument[] = [
  { id: 'nq', label: 'NQ', name: 'Nasdaq-100 futuro (NQ=F)', source: 'macro', macroKey: 'NASDAQ', spark: 'NQ=F', kind: 'index', href: '/ativo/NQ=F', staleAfterMin: 30 },
  { id: 'xau', label: 'XAU', name: 'Ouro futuro COMEX (GC=F)', source: 'macro', macroKey: 'GOLD', spark: 'GC=F', kind: 'usd', href: '/ativo/GC=F', staleAfterMin: 30 },
  {
    id: 'dxy',
    label: 'Dólar',
    name: 'Índice do dólar',
    source: 'macro',
    macroKey: 'DXY',
    spark: null,
    kind: 'index',
    staleAfterMin: 60 * 24 * 3,
    note: 'A API usa o índice amplo do Fed (DTWEXBGS), diário, e cai para o DXY da ICE quando o FRED está indisponível. As escalas são diferentes.',
  },
  { id: 'vix', label: 'VIX', name: 'Volatilidade implícita do S&P 500', source: 'macro', macroKey: 'VIX', spark: '^VIX', kind: 'index', href: '/ativo/%5EVIX', staleAfterMin: 60 * 24 * 3, note: 'Série diária do FRED; pode ter um dia útil de defasagem.' },
  { id: 'us10y', label: 'US10Y', name: 'Treasury 10 anos (yield)', source: 'macro', macroKey: 'US10Y', spark: '^TNX', kind: 'yield', staleAfterMin: 60 * 24 * 3, note: 'Série diária do FRED; pode ter um dia útil de defasagem.' },
  { id: 'usdbrl', label: 'USD/BRL', name: 'Dólar comercial', source: 'fx', spark: 'BRL=X', kind: 'brl', href: '/ativo/BRL=X', staleAfterMin: 60 * 24 },
];
