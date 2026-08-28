import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, String, Float, Integer, Boolean, DateTime, ForeignKey, Enum, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("user_id", "symbol", name="uq_watchlist_user_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("saas_workspaces.id"), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    label: Mapped[str] = mapped_column(String(64), default="")
    asset_type: Mapped[str] = mapped_column(String(24), default="equity")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    rules: Mapped[list["AlertRule"]] = relationship(back_populates="watchlist_item", cascade="all, delete-orphan")
    snapshots: Mapped[list["PriceSnapshot"]] = relationship(back_populates="watchlist_item", cascade="all, delete-orphan")


class RuleType(str, enum.Enum):
    PRICE_ABOVE = "PRICE_ABOVE"
    PRICE_BELOW = "PRICE_BELOW"
    PCT_CHANGE = "PCT_CHANGE"
    RSI_OVERBOUGHT = "RSI_OVERBOUGHT"
    RSI_OVERSOLD = "RSI_OVERSOLD"
    MA_CROSS_UP = "MA_CROSS_UP"
    MA_CROSS_DOWN = "MA_CROSS_DOWN"
    MACD_CROSS_UP = "MACD_CROSS_UP"
    MACD_CROSS_DOWN = "MACD_CROSS_DOWN"
    VOLUME_SPIKE = "VOLUME_SPIKE"


class RuleLogic(str, enum.Enum):
    ALL = "ALL"  # E - todas as condições precisam disparar
    ANY = "ANY"  # OU - basta uma condição disparar


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watchlist_item_id: Mapped[int] = mapped_column(ForeignKey("watchlist_items.id"))
    logic: Mapped[RuleLogic] = mapped_column(Enum(RuleLogic), default=RuleLogic.ALL)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    watchlist_item: Mapped["WatchlistItem"] = relationship(back_populates="rules")
    conditions: Mapped[list["AlertCondition"]] = relationship(
        back_populates="alert_rule", cascade="all, delete-orphan", order_by="AlertCondition.id"
    )


class AlertCondition(Base):
    __tablename__ = "alert_conditions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_rule_id: Mapped[int] = mapped_column(ForeignKey("alert_rules.id"))
    rule_type: Mapped[RuleType] = mapped_column(Enum(RuleType))
    threshold: Mapped[float] = mapped_column(Float, default=0.0)
    param_a: Mapped[int] = mapped_column(Integer, default=0)  # e.g. fast MA period, or window minutes
    param_b: Mapped[int] = mapped_column(Integer, default=0)  # e.g. slow MA period

    alert_rule: Mapped["AlertRule"] = relationship(back_populates="conditions")


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watchlist_item_id: Mapped[int] = mapped_column(ForeignKey("watchlist_items.id"), index=True)
    price: Mapped[float] = mapped_column(Float)
    change_pct: Mapped[float] = mapped_column(Float, default=0.0)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    watchlist_item: Mapped["WatchlistItem"] = relationship(back_populates="snapshots")


class MacroSnapshot(Base):
    """Periodic quote for one cross-asset instrument (DXY, US10Y, Gold, etc.),
    keyed by the friendly name from app.market_data.macro_data.MACRO_INSTRUMENTS.
    Powers the regime engine's macro overlay and cross-asset correlation reads.
    """

    __tablename__ = "macro_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(16), index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(64))
    price: Mapped[float] = mapped_column(Float)
    change_pct: Mapped[float] = mapped_column(Float, default=0.0)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AlertLog(Base):
    __tablename__ = "alert_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("saas_workspaces.id"), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    rule_type: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    delivered_telegram: Mapped[bool] = mapped_column(Boolean, default=False)


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    headline: Mapped[str] = mapped_column(String(512))
    summary: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(128), default="")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Nullable on purpose: this table is the raw archive being accumulated for the
    # future sentiment-vs-return experiment (see docs/data_phase_findings.md) — no
    # scorer writes to it yet. Backfilling scores for older rows once one exists is
    # just an UPDATE, not a schema change.
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)


class GlobalNewsItem(Base):
    __tablename__ = "global_news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(32), default="general", index=True)
    headline: Mapped[str] = mapped_column(String(512))
    summary: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(128), default="")
    impact_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)


class EconomicEvent(Base):
    __tablename__ = "economic_events"
    __table_args__ = (UniqueConstraint("event_name", "country", "event_date", name="uq_economic_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_name: Mapped[str] = mapped_column(String(256))
    country: Mapped[str] = mapped_column(String(64), default="")
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    impact: Mapped[str] = mapped_column(String(16), default="low")
    actual: Mapped[str] = mapped_column(String(64), default="")
    forecast: Mapped[str] = mapped_column(String(64), default="")
    previous: Mapped[str] = mapped_column(String(64), default="")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EarningsEvent(Base):
    __tablename__ = "earnings_events"
    __table_args__ = (UniqueConstraint("symbol", "event_date", name="uq_earnings_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    eps_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TransactionSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class SubscriptionPlan(str, enum.Enum):
    FREE = "FREE"
    PRO = "PRO"
    ADVISOR = "ADVISOR"


class NotificationChannelType(str, enum.Enum):
    TELEGRAM = "TELEGRAM"
    EMAIL = "EMAIL"
    WEBHOOK = "WEBHOOK"


class SaasWorkspace(Base):
    __tablename__ = "saas_workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(96), default="Meu workspace")
    brand_name: Mapped[str] = mapped_column(String(96), default="OneB")
    plan: Mapped[SubscriptionPlan] = mapped_column(Enum(SubscriptionPlan), default=SubscriptionPlan.FREE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    channels: Mapped[list["NotificationChannel"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    segments: Mapped[list["ClientSegment"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    report_templates: Mapped[list["ReportTemplate"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("saas_workspaces.id"), index=True)
    channel_type: Mapped[NotificationChannelType] = mapped_column(Enum(NotificationChannelType))
    destination: Mapped[str] = mapped_column(String(256))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    workspace: Mapped["SaasWorkspace"] = relationship(back_populates="channels")


class ClientSegment(Base):
    __tablename__ = "client_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("saas_workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(96))
    description: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    workspace: Mapped["SaasWorkspace"] = relationship(back_populates="segments")


class ReportTemplate(Base):
    __tablename__ = "report_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("saas_workspaces.id"), index=True)
    title: Mapped[str] = mapped_column(String(128))
    audience: Mapped[str] = mapped_column(String(96), default="Investidores")
    include_ai_summary: Mapped[bool] = mapped_column(Boolean, default=True)
    include_backtest: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    workspace: Mapped["SaasWorkspace"] = relationship(back_populates="report_templates")


class DecisionJournal(Base):
    __tablename__ = "decision_journals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    thesis: Mapped[str] = mapped_column(Text)
    trigger: Mapped[str] = mapped_column(String(512), default="")
    invalidation: Mapped[str] = mapped_column(String(512), default="")
    timeframe: Mapped[str] = mapped_column(String(64), default="")
    risk_notes: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Playbook(Base):
    __tablename__ = "playbooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(96))
    description: Mapped[str] = mapped_column(String(256), default="")
    rule_preset: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Transaction(Base):
    """Registro manual de compra/venda para acompanhamento de posição e P&L.

    Não integra com nenhuma corretora nem executa nada — é só contabilidade,
    o usuário digita o que já operou em outro lugar (ex: na Exness).
    """

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    side: Mapped[TransactionSide] = mapped_column(Enum(TransactionSide))
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    notes: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("saas_workspaces.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), default="")
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class ShareLink(Base):
    __tablename__ = "share_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("saas_workspaces.id"), nullable=True, index=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(128), default="Watchlist compartilhada")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TechnicalLevel(Base):
    __tablename__ = "technical_levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("saas_workspaces.id"), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    label: Mapped[str] = mapped_column(String(96), default="")
    kind: Mapped[str] = mapped_column(String(32), default="ZONE")
    price: Mapped[float] = mapped_column(Float)
    color: Mapped[str] = mapped_column(String(16), default="#60a5fa")
    notes: Mapped[str] = mapped_column(String(512), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class TradeSetup(Base):
    __tablename__ = "trade_setups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("saas_workspaces.id"), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    direction: Mapped[str] = mapped_column(String(8), default="LONG")
    entry_price: Mapped[float] = mapped_column(Float)
    stop_price: Mapped[float] = mapped_column(Float)
    target_price: Mapped[float] = mapped_column(Float)
    thesis: Mapped[str] = mapped_column(Text, default="")
    invalidation: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(32), default="PLANNED", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class RecommendationDecision(Base):
    __tablename__ = "recommendation_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("saas_workspaces.id"), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[float] = mapped_column(Float)
    suggested_size_pct: Mapped[float] = mapped_column(Float, default=0.0)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    thesis: Mapped[str] = mapped_column(Text, default="")
    fair_reason: Mapped[str] = mapped_column(Text, default="")
    invalidation: Mapped[str] = mapped_column(Text, default="")
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    memory_json: Mapped[str] = mapped_column(Text, default="{}")
    # Immutable prediction contract captured at decision time. This lets
    # calibration remain reproducible even after a live model changes.
    horizon: Mapped[str] = mapped_column(String(16), default="5d")
    direction: Mapped[str] = mapped_column(String(16), default="long")
    probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    uncertainty: Mapped[float | None] = mapped_column(Float, nullable=True)
    regime: Mapped[str] = mapped_column(String(32), default="UNKNOWN", index=True)
    model_id: Mapped[str] = mapped_column(String(64), default="decision_engine")
    model_version: Mapped[str] = mapped_column(String(32), default="v1")
    dataset_version: Mapped[str] = mapped_column(String(64), default="live")
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    prediction_json: Mapped[str] = mapped_column(Text, default="{}")
    data_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome_status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    outcome_return_1d_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome_return_5d_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome_return_20d_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome_1d_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome_20d_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Course(Base):
    __tablename__ = "lms_courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    modules: Mapped[list["CourseModule"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="CourseModule.order"
    )


class CourseModule(Base):
    __tablename__ = "lms_modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("lms_courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    order: Mapped[int] = mapped_column(Integer, default=0, index=True)

    course: Mapped["Course"] = relationship(back_populates="modules")
    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="module", cascade="all, delete-orphan", order_by="Lesson.order"
    )


class Lesson(Base):
    __tablename__ = "lms_lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("lms_modules.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    video_url: Mapped[str] = mapped_column(String(1024), default="")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)
    order: Mapped[int] = mapped_column(Integer, default=0, index=True)

    module: Mapped["CourseModule"] = relationship(back_populates="lessons")


class LessonProgress(Base):
    __tablename__ = "lms_lesson_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_lesson_progress_user_lesson"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lms_lessons.id"), index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LiveStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    LIVE = "LIVE"
    ENDED = "ENDED"


class LiveSession(Base):
    __tablename__ = "lms_live_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[LiveStatus] = mapped_column(Enum(LiveStatus), default=LiveStatus.SCHEDULED, index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    stream_url: Mapped[str] = mapped_column(String(1024), default="")
    replay_url: Mapped[str] = mapped_column(String(1024), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MorningReport(Base):
    """Snapshot of a generated 'análise matinal' (pre-market briefing).

    Stored so the dashboard can show today's report plus history, without
    recomputing it from live market data on every page view.
    """

    __tablename__ = "morning_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    narrative: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    delivered_telegram: Mapped[bool] = mapped_column(Boolean, default=False)
