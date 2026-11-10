// Mirrors app/schemas.py and app/models.py on the backend — keep in sync manually.

export type RuleType =
  | 'PRICE_ABOVE'
  | 'PRICE_BELOW'
  | 'PCT_CHANGE'
  | 'RSI_OVERBOUGHT'
  | 'RSI_OVERSOLD'
  | 'MA_CROSS_UP'
  | 'MA_CROSS_DOWN'
  | 'MACD_CROSS_UP'
  | 'MACD_CROSS_DOWN'
  | 'VOLUME_SPIKE';

export type RuleLogic = 'ALL' | 'ANY';

export type TransactionSide = 'BUY' | 'SELL';

export interface User {
  id: number;
  username: string;
  email: string | null;
  is_admin: boolean;
  created_at: string;
  /** Plano efetivo: "pro" também vale durante o teste grátis. */
  plan: 'free' | 'pro';
  paid: boolean;
  on_trial: boolean;
  trial_ends_at: string | null;
  telegram_linked: boolean;
}

export interface PlanLimits {
  max_symbols: number;
  max_rules: number;
}

export interface PlansInfo {
  free: PlanLimits & { name: string };
  pro: PlanLimits & { name: string; price_label: string; trial_days: number };
}

export interface BillingStatus {
  plan: 'free' | 'pro';
  paid: boolean;
  on_trial: boolean;
  trial_ends_at: string | null;
  subscription_status: string;
  current_period_end: string | null;
  limits: PlanLimits;
  checkout_enabled: boolean;
  has_customer: boolean;
}

export interface WatchlistItem {
  id: number;
  symbol: string;
  label: string;
  active: boolean;
}

export interface Condition {
  rule_type: RuleType;
  threshold: number;
  param_a: number;
  param_b: number;
}

export interface ConditionOut extends Condition {
  id: number;
}

export interface AlertRule {
  id: number;
  watchlist_item_id: number;
  logic: RuleLogic;
  active: boolean;
  cooldown_minutes: number;
  last_triggered_at: string | null;
  conditions: ConditionOut[];
}

export interface BacktestOccurrence {
  date: string;
  price: number;
  forward_return_pct: number | null;
}

export interface BacktestResult {
  trigger_count: number;
  avg_forward_return_pct: number | null;
  occurrences: BacktestOccurrence[];
}

export interface AlertLog {
  id: number;
  symbol: string;
  rule_type: string;
  message: string;
  triggered_at: string;
  delivered_telegram: boolean;
}

export interface NewsItem {
  symbol: string;
  headline: string;
  url: string;
  source: string;
  published_at: string;
}

export interface GlobalNewsItem {
  category: string;
  headline: string;
  summary: string;
  url: string;
  source: string;
  impact_score: number;
  published_at: string;
}

export interface FxQuote {
  pair: string;
  rate: number;
  change_pct: number;
  updated_at: string;
}

export interface CommodityQuote {
  symbol: string;
  name: string;
  unit: string;
  price: number;
  change_pct: number;
  updated_at: string;
}

export interface EconomicEvent {
  event_name: string;
  country: string;
  event_date: string;
  impact: string;
  forecast: string;
  previous: string;
}

export interface EarningsEvent {
  symbol: string;
  event_date: string;
  eps_estimate: number | null;
  revenue_estimate: number | null;
}

export interface Transaction {
  id: number;
  symbol: string;
  side: TransactionSide;
  quantity: number;
  price: number;
  executed_at: string;
  notes: string;
}

export interface PositionSummary {
  symbol: string;
  quantity: number;
  avg_cost: number;
  current_price: number | null;
  market_value: number | null;
  unrealized_pnl: number | null;
  realized_pnl: number;
}

export interface DashboardRow {
  id: number;
  symbol: string;
  label: string;
  price: number | null;
  change_pct: number | null;
  taken_at: string | null;
}

export interface DashboardSummary {
  rows: DashboardRow[];
  alerts: {
    symbol: string;
    message: string;
    triggered_at: string;
    delivered_telegram: boolean;
  }[];
}

export interface ChartData {
  symbol: string;
  timestamps: string[];
  open: (number | null)[];
  high: (number | null)[];
  low: (number | null)[];
  close: (number | null)[];
  volume: (number | null)[];
  rsi: (number | null)[];
  macd: (number | null)[];
  macd_signal: (number | null)[];
  ema_fast: (number | null)[];
  ema_slow: (number | null)[];
}

export interface CopilotVote {
  name: string;
  vote: string;
  confidence: number;
  summary: string;
  evidence: string[];
}

export interface CopilotAnalysis {
  symbol: string;
  question: string;
  bias: string;
  confidence: number;
  entry_price: number | null;
  votes: CopilotVote[];
  why: string[];
  contrary_view: string[];
  risk_plan: string[];
  simulation: {
    available: boolean;
    summary: string;
    metrics: Record<string, number>;
  };
  patterns: string[];
  disclaimer: string;
}

export interface TraderProfileGroup {
  key: string;
  trades: number;
  pnl: number;
  win_rate: number;
  avg_return_pct: number;
}

export interface TraderJournalEntry {
  symbol: string;
  entry_at: string;
  exit_at: string;
  quantity: number;
  avg_entry: number;
  exit_price: number;
  pnl: number;
  return_pct: number;
  holding_hours: number;
  lesson: string;
}

export interface PivotLevels {
  pivot: number;
  r1: number;
  r2: number;
  r3: number;
  s1: number;
  s2: number;
  s3: number;
}

export interface SymbolLevels {
  pivots: PivotLevels;
  swing_high: number | null;
  swing_low: number | null;
  prev_close: number | null;
}

export interface MorningReportIndex {
  key: string;
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  levels: SymbolLevels | null;
}

export interface MorningReportWatchlistRow {
  symbol: string;
  price: number | null;
  change_pct: number | null;
  levels: SymbolLevels | null;
}

export interface MorningReportData {
  date: string;
  indices: MorningReportIndex[];
  watchlist: MorningReportWatchlistRow[];
  overnight_news: { headline: string; source: string; impact_score: number }[];
  economic_events_today: { event_name: string; country: string }[];
  earnings_today: string[];
}

export interface MorningReport {
  id: number;
  generated_at: string;
  narrative: string;
  data: MorningReportData;
  delivered_telegram: boolean;
}

export interface TraderProfile {
  summary: {
    transactions: number;
    closed_trades: number;
    open_symbols: string[];
    total_pnl: number;
    win_rate: number;
    avg_win: number;
    avg_loss: number;
    expectancy: number;
    profit_factor: number;
    avg_holding_hours: number;
  };
  by_symbol: TraderProfileGroup[];
  by_hour: TraderProfileGroup[];
  by_style: TraderProfileGroup[];
  insights: string[];
  journal: TraderJournalEntry[];
}

export interface ResearchPair {
  a: string;
  b: string;
  r: number;
  n: number;
  p: number | null;
  p_adj: number | null;
  significant: boolean;
}

export interface ResearchDrift {
  a: string;
  b: string;
  r_full: number;
  r_recent: number;
  delta: number;
}

export interface ResearchEventRow {
  horizon: number;
  n: number;
  mean_pct: number | null;
  median_pct: number | null;
  hit_rate: number | null;
  baseline_mean_pct: number | null;
  excess_pct: number | null;
  t_stat: number | null;
}

export interface ResearchSymbol {
  bars: number;
  regime: {
    trend: string | null;
    trend_label: string | null;
    trend_bars: number;
    volatility: string | null;
    volatility_label: string | null;
    volatility_bars: number;
  };
  rsi_below_30: ResearchEventRow[];
  golden_cross: ResearchEventRow[];
}

export interface ResearchStudy {
  error?: string;
  symbols: string[];
  period?: [string, string];
  matrix?: (number | null)[][];
  pairs_tested?: number;
  pairs_significant?: number;
  top_correlations?: ResearchPair[];
  biggest_drifts?: ResearchDrift[];
  per_symbol?: Record<string, ResearchSymbol>;
  caveats?: string[];
}

export interface RiskPanel {
  symbol: string;
  as_of: string;
  price: number;
  regime: {
    trend: string | null;
    trend_label: string | null;
    trend_bars: number;
    volatility: string | null;
    volatility_label: string | null;
    volatility_bars: number;
  };
  volatility: { realized_20d_pct: number; atr_pct: number };
  levels: {
    dist_sma50_pct: number | null;
    dist_sma200_pct: number | null;
    drawdown_from_52w_high_pct: number;
  };
  sizing: {
    target_vol_pct: number;
    relative_exposure_pct: number;
    stop_atr_mult: number;
    stop_distance_pct: number;
    trailing_stop_price: number;
    stop_breached: boolean;
    risk_pct: number;
    position_pct_of_capital: number | null;
  };
  earnings: {
    next_date: string | null;
    days_until: number | null;
    soon: boolean;
    history: {
      events: number;
      avg_abs_move_pct: number;
      typical_day_move_pct: number;
      p05_pct: number;
      p95_pct: number;
      worst_pct: number;
      up_share_pct: number;
    } | null;
  };
  news: {
    count_7d: number;
    count_30d: number;
    archive_days: number;
    latest: { published_at: string; source: string; headline: string }[];
  };
  alerts: string[];
  evidence: string;
}

export interface SignalLog {
  started: string | null;
  entries: number;
  result: {
    symbols: { symbol: string; days: number; days_in_position: number; strategy_pct: number; buy_hold_pct: number }[];
    aggregate: {
      days: number;
      strategy_pct: number;
      buy_hold_pct: number;
      worst_day_strategy_pct: number;
      worst_day_buy_hold_pct: number;
    } | null;
  };
  recent: { date: string; symbol: string; state: number; close: number; trend: string }[];
}
