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
export type SubscriptionPlan = 'FREE' | 'PRO' | 'ADVISOR';
export type NotificationChannelType = 'TELEGRAM' | 'EMAIL' | 'WEBHOOK';
export type AssetType = 'equity' | 'etf' | 'index' | 'commodity' | 'fx' | 'bond_yield' | 'macro';

export interface User {
  id: number;
  username: string;
  is_admin: boolean;
  created_at: string;
}

export interface SaasWorkspace {
  id: number;
  name: string;
  brand_name: string;
  plan: SubscriptionPlan;
}

export interface NotificationChannel {
  id: number;
  channel_type: NotificationChannelType;
  destination: string;
  active: boolean;
}

export interface ClientSegment {
  id: number;
  name: string;
  description: string;
}

export interface ReportTemplate {
  id: number;
  title: string;
  audience: string;
  include_ai_summary: boolean;
  include_backtest: boolean;
}

export interface SaasOverview {
  workspace: SaasWorkspace;
  limits: Record<string, number>;
  usage: Record<string, number>;
  features: string[];
  channels: NotificationChannel[];
  segments: ClientSegment[];
  report_templates: ReportTemplate[];
}

export interface IntelligenceScore {
  symbol: string;
  score: number;
  label: string;
  factors: { name: string; impact: number; evidence: string }[];
}

export interface MovementExplanation {
  symbol: string;
  facts: string[];
  related_events: string[];
  hypotheses: string[];
}

export interface WeeklyBrief {
  title: string;
  summary: string[];
  top_opportunities: IntelligenceScore[];
  risks: IntelligenceScore[];
  next_events: Record<string, unknown>[];
}

export interface SignalQuality {
  symbol: string;
  alerts: number;
  delivered: number;
  noise_score: number;
  assessment: string;
}

export interface DecisionJournal {
  id: number;
  symbol: string;
  thesis: string;
  trigger: string;
  invalidation: string;
  timeframe: string;
  risk_notes: string;
  status: string;
  created_at: string;
}

export interface Playbook {
  id: number;
  name: string;
  description: string;
  rule_preset: string;
}

export interface DataQualityProvider {
  provider: string;
  available: boolean;
  price: number | null;
  change_pct: number | null;
  timestamp: string | null;
  error: string;
}

export interface DataQualityRow {
  symbol: string;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW';
  max_divergence_pct: number;
  freshest_age_minutes: number | null;
  issues: string[];
  providers: DataQualityProvider[];
}

export interface DataQualityOverview {
  rows: DataQualityRow[];
  confidence_counts: Record<'HIGH' | 'MEDIUM' | 'LOW', number>;
}

export interface OperationalHealth {
  status: string;
  generated_at: string;
  latest_snapshot_at: string | null;
  snapshot_age_minutes: number | null;
  db: {
    available: boolean;
    counts: Record<string, number>;
  };
  providers: Record<string, boolean>;
  jobs: Record<string, string | number>;
  data_quality: Record<'HIGH' | 'MEDIUM' | 'LOW', number>;
  market_cache: {
    ready: boolean;
    rows: { symbol: string; rows: number; has_ohlcv: boolean; last_close: number | null }[];
    files: Record<string, { exists: boolean; bytes: number; modified_at: string | null }>;
  };
  paper_simulator: {
    initial_capital: number | null;
    cash: number | null;
    portfolio_value: number | null;
    open_positions: number;
    closed_trades: number;
    status: string;
  };
  probability_model: {
    available: boolean;
    status: string;
    train_samples: number | null;
    holdout_accuracy: number | null;
    holdout_baseline_accuracy: number | null;
    recommendation: string;
  };
  automation: {
    verdict: string;
    long_ready?: boolean;
    short_ready?: boolean;
    recommendation: string;
  };
  last_simulation_validation: Record<string, unknown> | null;
  readiness: {
    level: string;
    trade_automation_allowed: boolean;
    blockers: string[];
    recommendation: string;
  };
  recent_alerts: { symbol: string; message: string; triggered_at: string }[];
  recent_audit_logs: { action: string; entity_type: string; entity_id: string; created_at: string }[];
}

export interface PaperLabEvent {
  at: string | null;
  type: string;
  title: string;
  symbol: string | null;
  decision: string | null;
  reason: string | null;
  price: number | null;
  shares: number | null;
  pnl: number | null;
  score: number | null;
  lesson: string;
}

export interface PaperLabPosition {
  symbol: string;
  entry_at: string | null;
  entry_price: number;
  shares: number;
  notional: number;
  stop: number | null;
  target: number | null;
  score: number | null;
  partial_taken: boolean;
  lesson: string;
}

export interface PaperLabStatus {
  generated_at: string;
  mode: string;
  status: string;
  headline: string;
  disclaimer: string;
  state: {
    initial_capital: number | null;
    cash: number | null;
    open_positions: number;
    closed_trades: number;
    positions: PaperLabPosition[];
  };
  latest_decision: PaperLabEvent | null;
  latest_calibration: {
    params?: Record<string, number>;
    signals?: number;
    precision_pct?: number;
    false_positive?: number;
    avg_5d_return_pct?: number;
    score?: number;
    status?: string;
    reason?: string;
  } | null;
  recent_events: PaperLabEvent[];
  validation: {
    generated_at: string | null;
    can_trade_now: boolean;
    decision_rule: string;
    risk_rule: string;
    market_data: { symbol: string; rows: number; has_ohlcv: boolean; last_close: number | null }[];
  };
  replay: {
    status: string | null;
    initial_capital: number | null;
    final_value: number | null;
    return_pct: number | null;
    buys: number | null;
    sells: number | null;
    closed_trades: number | null;
    win_rate_pct: number | null;
    profit_factor: number | null;
    max_drawdown_pct: number | null;
  } | null;
  readiness: {
    verdict: string | null;
    recommendation: string | null;
    trade_automation_allowed: boolean;
  };
  lesson_cards: { title: string; body: string }[];
}

export interface WatchlistItem {
  id: number;
  symbol: string;
  label: string;
  asset_type: AssetType;
  active: boolean;
}

export interface WatchlistPrice {
  id: number;
  symbol: string;
  label: string;
  asset_type: AssetType;
  price: number | null;
  change_pct: number | null;
  taken_at: string | null;
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
  win_rate_pct: number | null;
  profit_factor: number | null;
  max_drawdown_pct: number | null;
  buy_hold_return_pct: number | null;
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

export interface TechnicalLevel {
  id: number;
  symbol: string;
  label: string;
  kind: string;
  price: number;
  color: string;
  notes: string;
  active: boolean;
  created_at: string;
}

export interface TradeSetup {
  id: number;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  entry_price: number;
  stop_price: number;
  target_price: number;
  thesis: string;
  invalidation: string;
  status: string;
  created_at: string;
}

export interface TechnicalSignal {
  name: string;
  label: string;
  state: string;
  evidence: string;
}

export interface TechnicalAnalysis {
  symbol: string;
  price: number | null;
  change_pct: number | null;
  support: number | null;
  resistance: number | null;
  pivot: number | null;
  rsi: number | null;
  volume: number | null;
  avg_volume_20: number | null;
  atr_14: number | null;
  atr_pct: number | null;
  annualized_volatility_20: number | null;
  avg_range_pct_20: number | null;
  distance_to_support_pct: number | null;
  distance_to_resistance_pct: number | null;
  suggested_shares_200_usd: number;
  suggested_risk_usd_200: number | null;
  volatility_label: string;
  trend: string;
  bias: string;
  risk_reward: number | null;
  signals: TechnicalSignal[];
  levels: TechnicalLevel[];
  setups: TradeSetup[];
}

export interface DailyMarketAsset {
  symbol: string;
  label: string;
  price: number | null;
  change_pct: number | null;
  trend: string;
  bias: string;
  volatility_label: string;
  atr_pct: number | null;
  rsi: number | null;
  volume_ratio: number | null;
  distance_to_resistance_pct: number | null;
  distance_to_support_pct: number | null;
  score: number;
  notes: string[];
}

export interface DailyMarketSummary {
  generated_at: string;
  headline: string;
  market_tone: string;
  key_takeaways: string[];
  opportunities: DailyMarketAsset[];
  risks: DailyMarketAsset[];
  watch: DailyMarketAsset[];
  macro_events: {
    date: string;
    name: string;
    country: string;
    impact: string;
    forecast: string;
    previous: string;
  }[];
  top_news: {
    headline: string;
    source: string;
    category: string;
    impact_score: number;
    published_at: string;
    url: string;
  }[];
  action_plan: string[];
}

export interface DecisionDeskRecommendation {
  symbol: string;
  action: string;
  direction?: string;
  confidence: number;
  score: number;
  price: number;
  suggested_size_pct: number;
  stop_price: number | null;
  target_price: number | null;
  thesis: string;
  fair_reason: string;
  invalidation: string;
  evidence: string[];
  memory: Record<string, number>;
  score_details: Record<string, unknown>;
  ai_narrative: string | null;
  probability_win_pct: number | null;
}

export interface CircuitBreaker {
  tripped: boolean;
  samples: number;
  win_rate_pct: number | null;
}

export interface DecisionDesk {
  generated_at: string;
  headline: string;
  benchmark: string;
  recorded: number;
  skipped: string[];
  recommendations: DecisionDeskRecommendation[];
  circuit_breaker: CircuitBreaker;
  decision_health: {
    tripped: boolean;
    operating_mode: string;
    allowed: boolean;
    samples: number;
    win_rate_pct: number | null;
    calibration_error: number | null;
    reason: string;
  };
  calibration_source: string;
  short_calibration_source: string;
  macro_context: {
    dxy: number | null;
    dxy_change_20d_pct: number | null;
    oil: number | null;
    oil_change_20d_pct: number | null;
  };
}

export interface ReliabilityCalibrationBucket {
  label: string;
  samples: number;
  actual_win_rate_pct: number | null;
  midpoint_confidence: number;
}

export interface ReliabilityTrendPoint {
  period_label: string;
  samples: number;
  win_rate_pct: number;
  ends_at: string;
}

export interface ReliabilityScoreboard {
  total_samples: number;
  overall_win_rate_pct: number;
  calibration: ReliabilityCalibrationBucket[];
  trend: ReliabilityTrendPoint[];
}

export interface MarketDivergence {
  available: boolean;
  reason: string | null;
  today: string | null;
  yesterday: string | null;
  ai_lean_today: number | null;
  ai_lean_yesterday: number | null;
  ai_lean_change: number | null;
  benchmark_symbol: string | null;
  benchmark_move_pct: number | null;
  divergent: boolean | null;
  note: string | null;
}

export interface RecommendationDecision extends DecisionDeskRecommendation {
  id: number;
  outcome_status: string;
  outcome_return_1d_pct: number | null;
  outcome_return_5d_pct: number | null;
  outcome_return_20d_pct: number | null;
  regime: string;
  model_id: string;
  model_version: string;
  prediction: Record<string, unknown>;
  created_at: string;
}

export interface TechnicalEdgeRow {
  symbol: string;
  status: 'OK' | 'SEM_LEITURA';
  edge_score?: number;
  rank?: number;
  label?: 'OBSERVAR' | 'NEUTRO' | 'FRACO';
}

export interface TechnicalEdgeRanking {
  horizon_days: number;
  benchmark: string;
  universe: string[];
  research_note: string;
  rows: TechnicalEdgeRow[];
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
  trade_plan: {
    available: boolean;
    timeframe: string;
    reason: string;
    holding_window?: string;
    status?: string;
    entry_price?: number;
    stop_price?: number;
    target_1_price?: number;
    target_2_price?: number;
    risk_per_share_usd?: number;
    risk_amount_usd?: number;
    suggested_shares?: number;
    position_value_usd?: number;
    risk_reward_target_1?: number;
    risk_reward_target_2?: number;
    support_20d?: number;
    resistance_20d?: number;
    atr_14?: number | null;
    invalidation?: string;
  };
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

export interface LessonSummary {
  id: number;
  title: string;
  description: string;
  video_url: string;
  duration_minutes: number;
  order: number;
  completed: boolean;
  summary: string;
  checklist: string[];
  exercise: string;
  required: boolean;
}

export interface CourseModuleSummary {
  id: number;
  title: string;
  order: number;
  lessons: LessonSummary[];
}

export interface CourseDetail {
  id: number;
  slug: string;
  title: string;
  description: string;
  order: number;
  lesson_count: number;
  completed_count: number;
  modules: CourseModuleSummary[];
}

export type LiveStatus = 'SCHEDULED' | 'LIVE' | 'ENDED';

export interface LiveSession {
  id: number;
  title: string;
  description: string;
  status: LiveStatus;
  scheduled_at: string;
  stream_url: string;
  replay_url: string;
}

export interface CourseSummary {
  id: number;
  slug: string;
  title: string;
  description: string;
  order: number;
  lesson_count: number;
  completed_count: number;
}

export interface LearningRecommendation {
  reason: string;
  course_slug: string;
  course_title: string;
  lesson_id: number;
  lesson_title: string;
  gap: string;
}

export interface CertificateStatus {
  eligible: boolean;
  progress_pct: number;
  completed_required_lessons: number;
  required_lessons: number;
  completed_simulations: number;
  required_simulations: number;
  next_requirement: string;
}

export interface LearningState {
  courses: CourseSummary[];
  recommendation: LearningRecommendation | null;
  certificate: CertificateStatus;
}

// ---- Regime / macro (app/routers/regime.py) ----
export interface RegimeFactor {
  name: string;
  impact: number | null;
  evidence: string;
}

export interface LocalRegime {
  label: 'STRONG BULL' | 'BULL' | 'NEUTRAL' | 'BEAR' | 'STRONG BEAR' | string;
  score: number;
  factors: RegimeFactor[];
}

export interface CrossAssetRow {
  key: string;
  name: string;
  correlation_30d: number;
  relevance: 'ALTA' | 'MEDIA' | 'BAIXA';
  direction: 'CONFIRMANDO' | 'DIVERGINDO' | null;
  change_pct_latest: number | null;
}

export interface RegimeReport {
  symbol: string;
  local_regime: LocalRegime | null;
  macro_context: 'POSITIVO' | 'NEUTRO' | 'NEGATIVO';
  cross_asset_relevance: CrossAssetRow[];
}

export interface MacroInstrument {
  key: string;
  symbol: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  taken_at: string | null;
  /** Presentes nas versões do backend com radar de tendências. */
  context?: string | null;
  trend?: TrendAnalysis | null;
}

export type TrendDirection = 'ALTA FORTE' | 'ALTA' | 'LATERAL' | 'BAIXA' | 'BAIXA FORTE';

export interface TrendAnalysis {
  direction: TrendDirection;
  score: number;
  strength: 'FORTE' | 'MODERADA' | 'FRACA' | 'INDEFINIDA';
  adx14: number | null;
  change_5d: number | null;
  change_20d: number | null;
  change_60d: number | null;
  change_unit: '%' | 'bps';
  last: number;
  ema20: number;
  ema50: number;
  as_of: string;
  age_days: number;
}

export interface CorrelationPair {
  left: string;
  right: string;
  correlation: number;
  observations: number;
}

export interface CorrelationWindow {
  sessions: number;
  minimum_observations: number;
  matrix: Array<{ key: string; values: Record<string, number | null> }>;
  strongest_positive: CorrelationPair[];
  strongest_negative: CorrelationPair[];
}

export interface RelationshipDynamic {
  left: string;
  right: string;
  correlation_20d: number;
  correlation_60d: number;
  delta: number;
  strength_delta: number;
  status: 'INVERSAO' | 'FORTALECENDO' | 'ENFRAQUECENDO' | 'ESTAVEL';
}

export interface LeadLagCandidate {
  leader: string;
  follower: string;
  lag_sessions: number;
  correlation: number;
  contemporaneous_correlation: number | null;
  improvement: number;
  observations: number;
}

export interface LeadLagValidation {
  leader: string;
  follower: string;
  lag_sessions: number;
  observations_days: number;
  persistence_pct: number;
  average_correlation: number;
  last_seen: string;
  status: 'RECORRENTE' | 'OBSERVACAO';
}

export interface NewsContext {
  window_start: string;
  window_end: string;
  article_count: number;
  high_impact_count: number;
  impact_sum: number;
  average_impact: number | null;
  maximum_impact: number | null;
  mean_sentiment: number | null;
  sentiment_observations: number;
  sentiment_coverage_pct: number;
  theme_counts: Record<string, number>;
  top_headlines: Array<{ headline: string; source: string; impact_score: number; sentiment_score: number | null; published_at: string; url: string }>;
}

export interface NewsMarketCorrelation {
  factor_type: 'INTENSIDADE' | 'SENTIMENTO' | 'TEMA';
  factor: string;
  asset: string;
  target: 'MAGNITUDE' | 'DIRECAO';
  correlation: number;
  observations: number;
  direction: 'POSITIVA' | 'NEGATIVA';
  status: 'EXPLORATORIO';
}

export interface NewsMarketAnalysis {
  method: string;
  minimum_observations: number;
  available_forward_pairs: number;
  sessions_recorded?: number;
  news_days?: number;
  coverage_pct?: number;
  expected_sessions_approx?: number;
  session_coverage_pct?: number;
  status: 'PRONTO' | 'COLETANDO_HISTORICO';
  correlations: NewsMarketCorrelation[];
  warnings: string[];
  windows?: Partial<Record<'3m' | '6m' | '12m', NewsMarketAnalysis>>;
}

export interface MacroHistoryStatus {
  days_recorded: number;
  latest: {
    snapshot_date: string;
    captured_at: string;
    coverage_pct: number;
    fresh_count: number;
    stale_count: number;
    missing_count: number;
  } | null;
  lead_lag_validation: LeadLagValidation[];
  latest_news_context?: NewsContext | null;
  news_market_analysis?: NewsMarketAnalysis;
}

export interface MacroOverview {
  instruments: MacroInstrument[];
  trend_watchlist?: MacroInstrument[];
  correlation_windows?: Partial<Record<'20' | '60' | '3m' | '6m' | '12m', CorrelationWindow>>;
  relationship_dynamics?: RelationshipDynamic[];
  lead_lag_candidates?: LeadLagCandidate[];
  history_status?: MacroHistoryStatus;
  nasdaq_cross_asset_relevance: CrossAssetRow[];
}
