from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import RuleLogic, RuleType, TransactionSide


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None = None
    is_admin: bool
    created_at: datetime
    plan: str = "free"  # plano efetivo (Pro durante o teste conta como Pro)
    paid: bool = False
    on_trial: bool = False
    trial_ends_at: datetime | None = None
    telegram_linked: bool = False


class LoginRequest(BaseModel):
    username: str  # aceita usuário ou e-mail
    password: str


class CadastroRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8)
    accept_terms: bool = False


class UsuarioCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8)
    is_admin: bool = False


class PlanUpdateRequest(BaseModel):
    plan: str = Field(pattern="^(free|pro)$")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class WatchlistItemCreate(BaseModel):
    symbol: str
    label: str = ""


class WatchlistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    label: str
    active: bool


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
