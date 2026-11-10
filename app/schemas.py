from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import NotificationChannelType, RuleLogic, RuleType, SubscriptionPlan, TransactionSide


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_admin: bool
    created_at: datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class CadastroRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8)


class PasswordResetRequest(BaseModel):
    """Nova senha definida por um admin para um usuario existente.

    Reset, nao recriacao: o id do usuario e referenciado por watchlist, posicoes,
    alertas e historico -- apagar e recriar a conta descartaria tudo isso em silencio.
    """

    password: str = Field(min_length=8, max_length=128)


class UsuarioCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8)
    is_admin: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class WorkspaceUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=96)
    brand_name: str = Field(min_length=2, max_length=96)


class PlanUpdate(BaseModel):
    plan: SubscriptionPlan


class NotificationChannelCreate(BaseModel):
    channel_type: NotificationChannelType
    destination: str = Field(min_length=3, max_length=256)


class NotificationChannelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_type: NotificationChannelType
    destination: str
    active: bool


class ClientSegmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=96)
    description: str = ""


class ClientSegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str


class ReportTemplateCreate(BaseModel):
    title: str = Field(min_length=2, max_length=128)
    audience: str = Field(default="Investidores", max_length=96)
    include_ai_summary: bool = True
    include_backtest: bool = False


class ReportTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    audience: str
    include_ai_summary: bool
    include_backtest: bool


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    brand_name: str
    plan: SubscriptionPlan


class SaasOverviewOut(BaseModel):
    workspace: WorkspaceOut
    limits: dict[str, int]
    usage: dict[str, int]
    features: list[str]
    channels: list[NotificationChannelOut]
    segments: list[ClientSegmentOut]
    report_templates: list[ReportTemplateOut]


class DecisionJournalCreate(BaseModel):
    symbol: str
    thesis: str = Field(min_length=5)
    trigger: str = ""
    invalidation: str = ""
    timeframe: str = ""
    risk_notes: str = ""


class DecisionJournalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    thesis: str
    trigger: str
    invalidation: str
    timeframe: str
    risk_notes: str
    status: str
    created_at: datetime


class PlaybookCreate(BaseModel):
    name: str = Field(min_length=3, max_length=96)
    description: str = ""
    rule_preset: str = ""


class PlaybookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    rule_preset: str


class WatchlistItemCreate(BaseModel):
    symbol: str
    label: str = ""
    asset_type: str = Field(default="equity", max_length=24)


class WatchlistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    label: str
    asset_type: str
    active: bool


class WatchlistPriceOut(BaseModel):
    id: int
    symbol: str
    label: str
    asset_type: str
    price: float | None
    change_pct: float | None
    taken_at: datetime | None


class ConditionCreate(BaseModel):
    rule_type: RuleType
    threshold: float = 0.0
    param_a: int = 0
    param_b: int = 0


class ConditionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_type: RuleType
    threshold: float
    param_a: int
    param_b: int


class AlertRuleCreate(BaseModel):
    watchlist_item_id: int
    logic: RuleLogic = RuleLogic.ALL
    cooldown_minutes: int = 60
    conditions: list[ConditionCreate]


class AlertRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    watchlist_item_id: int
    logic: RuleLogic
    active: bool
    cooldown_minutes: int
    last_triggered_at: datetime | None
    conditions: list[ConditionOut]


class BacktestRequest(BaseModel):
    symbol: str
    logic: RuleLogic = RuleLogic.ALL
    conditions: list[ConditionCreate]
    period: str = "3mo"
    interval: str = "1d"
    forward_bars: int = 5


class BacktestOccurrence(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: str
    price: float
    forward_return_pct: float | None


class BacktestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trigger_count: int
    avg_forward_return_pct: float | None
    occurrences: list[BacktestOccurrence]
    win_rate_pct: float | None = None
    profit_factor: float | None = None
    max_drawdown_pct: float | None = None
    buy_hold_return_pct: float | None = None


class TechnicalLevelCreate(BaseModel):
    symbol: str
    label: str = Field(default="", max_length=96)
    kind: str = Field(default="ZONE", max_length=32)
    price: float
    color: str = Field(default="#60a5fa", max_length=16)
    notes: str = Field(default="", max_length=512)


class TechnicalLevelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    label: str
    kind: str
    price: float
    color: str
    notes: str
    active: bool
    created_at: datetime


class TradeSetupCreate(BaseModel):
    symbol: str
    direction: str = Field(default="LONG", max_length=8)
    entry_price: float
    stop_price: float
    target_price: float
    thesis: str = ""
    invalidation: str = ""


class TradeSetupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    direction: str
    entry_price: float
    stop_price: float
    target_price: float
    thesis: str
    invalidation: str
    status: str
    created_at: datetime


class TechnicalSignalOut(BaseModel):
    name: str
    label: str
    state: str
    evidence: str


class TechnicalAnalysisOut(BaseModel):
    symbol: str
    price: float | None
    change_pct: float | None
    support: float | None
    resistance: float | None
    pivot: float | None
    rsi: float | None
    volume: float | None
    avg_volume_20: float | None
    atr_14: float | None
    atr_pct: float | None
    annualized_volatility_20: float | None
    avg_range_pct_20: float | None
    distance_to_support_pct: float | None
    distance_to_resistance_pct: float | None
    suggested_shares_200_usd: int
    suggested_risk_usd_200: float | None
    volatility_label: str
    trend: str
    bias: str
    risk_reward: float | None
    signals: list[TechnicalSignalOut]
    levels: list[TechnicalLevelOut]
    setups: list[TradeSetupOut]


class DailyMarketAssetOut(BaseModel):
    symbol: str
    label: str
    price: float | None
    change_pct: float | None
    trend: str
    bias: str
    volatility_label: str
    atr_pct: float | None
    rsi: float | None
    volume_ratio: float | None
    distance_to_resistance_pct: float | None
    distance_to_support_pct: float | None
    score: int
    notes: list[str]


class DailyMarketSummaryOut(BaseModel):
    generated_at: datetime
    headline: str
    market_tone: str
    key_takeaways: list[str]
    opportunities: list[DailyMarketAssetOut]
    risks: list[DailyMarketAssetOut]
    watch: list[DailyMarketAssetOut]
    macro_events: list[dict[str, str]]
    top_news: list[dict[str, str | int]]
    action_plan: list[str]


class DecisionDeskRecommendationOut(BaseModel):
    symbol: str
    action: str
    direction: str
    confidence: int
    score: int
    price: float
    suggested_size_pct: float
    stop_price: float | None
    target_price: float | None
    thesis: str
    fair_reason: str
    invalidation: str
    evidence: list[str]
    memory: dict
    score_details: dict
    ai_narrative: str | None = None
    probability_win_pct: float | None = None
    quality_gate: dict | None = None
    prediction: dict | None = None
    risk: dict | None = None
    decision_card: dict | None = None


class CircuitBreakerOut(BaseModel):
    tripped: bool
    samples: int
    win_rate_pct: float | None


class DecisionHealthOut(BaseModel):
    tripped: bool
    operating_mode: str
    allowed: bool
    samples: int
    win_rate_pct: float | None
    calibration_error: float | None
    reason: str


class DecisionDeskOut(BaseModel):
    generated_at: datetime
    headline: str
    benchmark: str
    recorded: int
    skipped: list[str]
    recommendations: list[DecisionDeskRecommendationOut]
    circuit_breaker: CircuitBreakerOut
    decision_health: DecisionHealthOut
    calibration_source: str
    short_calibration_source: str
    macro_context: dict


class ReliabilityCalibrationBucketOut(BaseModel):
    label: str
    samples: int
    actual_win_rate_pct: float | None
    midpoint_confidence: float


class ReliabilityTrendPointOut(BaseModel):
    period_label: str
    samples: int
    win_rate_pct: float
    ends_at: datetime


class ReliabilityScoreboardOut(BaseModel):
    total_samples: int
    overall_win_rate_pct: float
    calibration: list[ReliabilityCalibrationBucketOut]
    trend: list[ReliabilityTrendPointOut]


class ModelHealthEntryOut(BaseModel):
    trained_at: str
    train_samples: int | None
    train_accuracy: float | None
    holdout_samples: int | None
    holdout_accuracy: float | None


class ModelHealthOut(BaseModel):
    model_present: bool
    latest: ModelHealthEntryOut | None
    history: list[ModelHealthEntryOut]
    drift_alert: bool
    drift_alert_threshold: float


class MarketDivergenceOut(BaseModel):
    available: bool
    reason: str | None = None
    today: str | None = None
    yesterday: str | None = None
    ai_lean_today: float | None = None
    ai_lean_yesterday: float | None = None
    ai_lean_change: float | None = None
    benchmark_symbol: str | None = None
    benchmark_move_pct: float | None = None
    divergent: bool | None = None
    note: str | None = None


class RecommendationDecisionOut(BaseModel):
    id: int
    symbol: str
    action: str
    confidence: int
    score: int
    price: float
    suggested_size_pct: float
    stop_price: float | None
    target_price: float | None
    thesis: str
    fair_reason: str
    invalidation: str
    evidence: list[str]
    memory: dict
    outcome_status: str
    outcome_return_1d_pct: float | None
    outcome_return_5d_pct: float | None
    outcome_return_20d_pct: float | None
    regime: str
    model_id: str
    model_version: str
    prediction: dict
    created_at: datetime


class AlertLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    rule_type: str
    message: str
    triggered_at: datetime
    delivered_telegram: bool


class PriceSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    price: float
    change_pct: float
    volume: float
    taken_at: datetime


class TransactionCreate(BaseModel):
    symbol: str
    side: TransactionSide
    quantity: float
    price: float
    executed_at: datetime
    notes: str = ""


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    side: TransactionSide
    quantity: float
    price: float
    executed_at: datetime
    notes: str


class PositionSummaryOut(BaseModel):
    symbol: str
    quantity: float
    avg_cost: float
    current_price: float | None
    market_value: float | None
    unrealized_pnl: float | None
    realized_pnl: float


class AssistantMessage(BaseModel):
    role: str
    text: str


class AssistantAskRequest(BaseModel):
    question: str
    history: list[AssistantMessage] = Field(default_factory=list)


class AssistantAskResponse(BaseModel):
    answer: str


class CopilotAnalyzeRequest(BaseModel):
    symbol: str
    question: str = ""
    capital_usd: float = Field(default=20000, gt=0)
    risk_budget_pct: float = Field(default=1, gt=0, le=10)


class LessonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    video_url: str
    duration_minutes: int
    order: int
    completed: bool = False
    summary: str = ""
    checklist: list[str] = Field(default_factory=list)
    exercise: str = ""
    required: bool = True


class ModuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    order: int
    lessons: list[LessonOut] = Field(default_factory=list)


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    description: str
    order: int
    lesson_count: int = 0
    completed_count: int = 0
    modules: list[ModuleOut] = Field(default_factory=list)


class CourseSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    description: str
    order: int
    lesson_count: int = 0
    completed_count: int = 0


class LearningRecommendationOut(BaseModel):
    reason: str
    course_slug: str
    course_title: str
    lesson_id: int
    lesson_title: str
    gap: str


class CertificateStatusOut(BaseModel):
    eligible: bool
    progress_pct: int
    completed_required_lessons: int
    required_lessons: int
    completed_simulations: int
    required_simulations: int
    next_requirement: str


class LearningStateOut(BaseModel):
    courses: list[CourseSummaryOut]
    recommendation: LearningRecommendationOut | None = None
    certificate: CertificateStatusOut


class LiveSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: str
    scheduled_at: datetime
    stream_url: str
    replay_url: str


class LiveSessionCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = ""
    scheduled_at: datetime
    stream_url: str = ""


class LiveSessionStatusUpdate(BaseModel):
    status: str
    replay_url: str = ""
