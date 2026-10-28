/** Yahoo symbols supported by the chart API. Broker aliases are labels only. */
export interface ChartAsset {
  id: string;
  symbol: string;
  label: string;
  option: string;
  group: string;
  note: string;
}

const future = (id: string, symbol: string, label: string, option = label, group = 'Índices futuros'): ChartAsset => ({
  id, symbol, label, option, group,
  note: `Referência: contrato futuro ${symbol}. O preço pode diferir do índice à vista e do CFD da sua corretora.`,
});
const fx = (id: string, symbol: string, pair: string): ChartAsset => ({
  id, symbol, label: pair, option: pair, group: 'Moedas (Forex)',
  note: `Referência cambial ${pair} (${symbol}). A cotação pode diferir da sua corretora.`,
});
const crypto = (id: string, symbol: string, label: string, pair: string): ChartAsset => ({
  id, symbol, label: `${label} / dólar`, option: `${pair} · ${label}`, group: 'Criptomoedas',
  note: `${label} em dólar (${symbol}). A cotação pode diferir entre exchanges e corretoras.`,
});
const equity = (id: string, symbol: string, label: string, brazil = false): ChartAsset => ({
  id, symbol, label, option: `${symbol.replace('.SA', '')} · ${label}`,
  group: brazil ? 'Brasil (B3)' : 'Ações dos EUA',
  note: `${label} (${symbol}), em ${brazil ? 'reais' : 'dólares'}. Dados podem ter atraso e seguem o horário da bolsa.`,
});

export const CHART_ASSETS: readonly ChartAsset[] = [
  future('nasdaq', 'NQ=F', 'Nasdaq-100 futuro', 'NASDAQ · Nasdaq-100'),
  future('sp500', 'ES=F', 'S&P 500 futuro', 'S&P 500'),
  future('dowjones', 'YM=F', 'Dow Jones futuro', 'Dow Jones'),
  future('russell', 'RTY=F', 'Russell 2000 futuro', 'Russell 2000'),
  {
    id: 'xauusd', symbol: 'GC=F', label: 'Ouro futuro', option: 'XAUUSD · Ouro', group: 'Metais e energia',
    note: 'Referência: ouro futuro COMEX (GC=F), em USD por onça. Não é a cotação spot XAUUSD da sua corretora.',
  },
  future('xagusd', 'SI=F', 'Prata futura', 'XAGUSD · Prata (futuro)', 'Metais e energia'),
  future('wti', 'CL=F', 'Petróleo WTI futuro', 'Petróleo WTI', 'Metais e energia'),
  future('gas', 'NG=F', 'Gás natural futuro', 'Gás natural', 'Metais e energia'),
  fx('eurusd', 'EURUSD=X', 'EUR/USD'),
  fx('gbpusd', 'GBPUSD=X', 'GBP/USD'),
  fx('usdjpy', 'JPY=X', 'USD/JPY'),
  fx('audusd', 'AUDUSD=X', 'AUD/USD'),
  fx('usdcad', 'CAD=X', 'USD/CAD'),
  fx('usdbrl', 'BRL=X', 'USD/BRL'),
  crypto('btcusd', 'BTC-USD', 'Bitcoin', 'BTCUSD'),
  crypto('ethusd', 'ETH-USD', 'Ethereum', 'ETHUSD'),
  crypto('solusd', 'SOL-USD', 'Solana', 'SOLUSD'),
  crypto('xrpusd', 'XRP-USD', 'XRP', 'XRPUSD'),
  equity('aapl', 'AAPL', 'Apple'),
  equity('msft', 'MSFT', 'Microsoft'),
  equity('nvda', 'NVDA', 'Nvidia'),
  equity('amzn', 'AMZN', 'Amazon'),
  equity('googl', 'GOOGL', 'Alphabet'),
  equity('tsla', 'TSLA', 'Tesla'),
  {
    id: 'ibovespa', symbol: '^BVSP', label: 'Ibovespa', option: 'IBOV · Ibovespa', group: 'Brasil (B3)',
    note: 'Índice Ibovespa à vista (^BVSP), em pontos. Não é o contrato futuro WIN/IND.',
  },
  equity('bova11', 'BOVA11.SA', 'ETF Ibovespa', true),
  equity('petr4', 'PETR4.SA', 'Petrobras', true),
  equity('vale3', 'VALE3.SA', 'Vale', true),
  equity('itub4', 'ITUB4.SA', 'Itaú Unibanco', true),
];

export const CHART_ASSET_GROUPS = [...new Set(CHART_ASSETS.map((asset) => asset.group))];
