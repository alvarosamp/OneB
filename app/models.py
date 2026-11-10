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

    email: Mapped[str | None] = mapped_column(String(254), unique=True, index=True, nullable=True)
    accepted_terms_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Plano e cobrança (ver app/billing.py). "free" | "pro"; o plano efetivo também considera
    # o período de teste e o status da assinatura no Stripe.
    plan: Mapped[str] = mapped_column(String(16), default="free")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subscription_status: Mapped[str] = mapped_column(String(24), default="")
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Telegram por usuário: o chat é vinculado com um código de uso único (/vincular CODIGO).
    telegram_chat_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    telegram_link_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("user_id", "symbol", name="uq_watchlist_user_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    label: Mapped[str] = mapped_column(String(64), default="")
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


class AlertLog(Base):
    __tablename__ = "alert_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
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


class Transaction(Base):
    """Registro manual de compra/venda para acompanhamento de posição e P&L.

    Não integra com nenhuma corretora nem executa nada — é só contabilidade,
    o usuário digita o que já operou em outro lugar (ex: na Exness).
    """

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    side: Mapped[TransactionSide] = mapped_column(Enum(TransactionSide))
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    notes: Mapped[str] = mapped_column(String(256), default="")
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
