/** Respostas de /api/brasil/* (ver app/routers/brasil.py). */

export interface Rates {
  selic: number;
  cdi: number;
  ipca_12m: number;
  poupanca: number;
  real_cdi: number;
  stale: boolean;
  source: string;
  series: Record<string, { value: number; as_of: string; code: number }>;
}

export interface Product {
  key: string;
  label: string;
  group: 'renda_fixa' | 'renda_variavel';
  what: string;
  risk: number;
  risk_label: string;
  liquidity: string;
  guarantee: string;
  tax: string;
  minimum: string;
  good_for: string;
  watch_out: string;
}

export interface AllocationItem {
  key: string;
  label: string;
  pct: number;
  group: Product['group'];
  risk: number;
  initial_amount: number;
  monthly_amount: number;
  /** Mês em que o aporte desta parte começa (depois de completar a reserva). */
  monthly_from: number;
  liquidity: string;
  guarantee: string;
  tax: string;
  reason: string;
}

export interface TimelinePoint {
  month: number;
  invested: number;
  p10: number;
  p50: number;
  p90: number;
  poupanca: number;
}

export interface Simulation {
  profile: { key: string; label: string; text: string; factors: string[] };
  horizon: 'curto' | 'medio' | 'longo';
  steps: { title: string; text: string }[];
  reserve: { target: number; months_to_fill: number } | null;
  allocation: AllocationItem[];
  projection: {
    months: number;
    years: number;
    invested: number;
    p10: number;
    median: number;
    p90: number;
    median_today_money: number;
    poupanca: number;
    vs_poupanca: number;
    loss_probability: number;
    has_variable: boolean;
    timeline: TimelinePoint[];
  };
  assumptions: {
    selic: number;
    cdi: number;
    ipca_12m: number;
    poupanca: number;
    ipca_real_rate: number;
    prefixado_rate: number;
    variable: Record<string, { premium_over_cdi: number; volatility_pct: number }>;
    rates_as_of: string | null;
    rates_stale: boolean;
    scenarios: number;
  };
  warnings: string[];
  disclaimer: string;
}

export interface MarketRow {
  symbol: string;
  label: string;
  group: 'indice' | 'etf' | 'acao' | 'fii';
  description: string;
  available: boolean;
  price?: number;
  change_pct?: number;
  return_12m_pct?: number | null;
  volatility_pct?: number;
  max_drawdown_pct?: number;
  dividend_yield_pct?: number | null;
  data_break?: string | null;
  stale?: boolean;
  as_of?: string;
}

export interface MarketSnapshot {
  rows: MarketRow[];
  source: string;
  note: string;
}

export interface History {
  table: ({ months: number } & Partial<Record<'cdi' | 'ipca' | 'ibovespa' | 'dolar' | 'poupanca', number | null>>)[];
  last_month: string | null;
  missing: string[];
  note: string;
}

export interface BrEvent {
  date: string;
  kind: 'copom' | 'fomc' | 'eleicao' | 'ipca' | 'vencimento';
  title: string;
  why: string;
  impact: string;
  approximate: boolean;
}

export interface ImpactGroup {
  n: number;
  mean_abs_pct?: number;
  ratio?: number | null;
  rows: { event_date: string; session: string; label: string; return_pct: number }[];
}

export interface EventsData {
  upcoming: BrEvent[];
  impact: { available: boolean; since?: string; normal_abs_pct?: number; copom?: ImpactGroup; fomc?: ImpactGroup; eleicao?: ImpactGroup; note?: string };
}
