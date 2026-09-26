from datetime import datetime, timedelta, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import indicators
from app.auth import get_current_user
from app.db import get_db
from app.market_data import service as market_data_service
from app.market_data import yfinance_client
from app.models import (
    AlertLog,
    EarningsEvent,
    EconomicEvent,
    GlobalNewsItem,
    NewsItem,
    PriceSnapshot,
    User,
    WatchlistItem,
)
from app.saas import get_or_create_workspace
from app.schemas import AlertLogOut

router = APIRouter(prefix="/api", tags=["api"], dependencies=[Depends(get_current_user)])


def _json_list(series: pd.Series, decimals: int) -> list[float | None]:
    """Convert a pandas Series to a JSON-safe list (NaN -> None)."""
    rounded = series.round(decimals)
    return [None if pd.isna(v) else float(v) for v in rounded]


@router.get("/chart/{symbol}")
def chart_data(symbol: str, period: str = "5d", interval: str = "15m"):
    history = market_data_service.get_bars(symbol.upper(), period=period, interval=interval)
    if history.empty:
        raise HTTPException(status_code=404, detail="Sem dados históricos para este símbolo")

    close = history["close"]
    rsi_series = indicators.rsi(close)
    macd_df = indicators.macd(close)
    ema_fast = indicators.ema(close, 9)
    ema_slow = indicators.ema(close, 21)

    return {
        "symbol": symbol.upper(),
        "timestamps": [ts.isoformat() for ts in history.index],
        "open": _json_list(history["open"], 2),
        "high": _json_list(history["high"], 2),
        "low": _json_list(history["low"], 2),
        "close": _json_list(close, 2),
        "volume": _json_list(history["volume"], 0),
        "rsi": _json_list(rsi_series, 2),
        "macd": _json_list(macd_df["macd"], 3),
        "macd_signal": _json_list(macd_df["signal"], 3),
        "ema_fast": _json_list(ema_fast, 2),
        "ema_slow": _json_list(ema_slow, 2),
    }


@router.get("/fx/usd-brl")
def usd_brl_quote():
    quote = yfinance_client.get_usd_brl_quote()
    if quote is None:
        raise HTTPException(status_code=404, detail="Sem dados de cambio USD/BRL")
    return {
        "pair": quote.pair,
        "rate": round(quote.rate, 4),
        "change_pct": round(quote.change_pct, 2),
        "updated_at": quote.updated_at.isoformat(),
    }


@router.get("/commodities/gold")
def gold_quote():
    quote = yfinance_client.get_gold_quote()
    if quote is None:
        raise HTTPException(status_code=404, detail="Sem dados de ouro")
    return {
        "symbol": quote.symbol,
        "name": quote.name,
        "unit": quote.unit,
        "price": round(quote.price, 2),
        "change_pct": round(quote.change_pct, 2),
        "updated_at": quote.updated_at.isoformat(),
    }


@router.get("/alerts", response_model=list[AlertLogOut])
def list_alerts(
    limit: int = 50,
    symbol: str | None = None,
    rule_type: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(AlertLog).filter((AlertLog.user_id == user.id) | (AlertLog.user_id.is_(None)))
    if symbol:
        query = query.filter(AlertLog.symbol == symbol.upper())
    if rule_type:
        # rule_type agora pode ser um rótulo composto ("RSI_OVERBOUGHT+VOLUME_SPIKE"),
        # então usa "contains" em vez de igualdade pra achar regras compostas também.
        query = query.filter(AlertLog.rule_type.contains(rule_type))
    return query.order_by(AlertLog.triggered_at.desc()).limit(limit).all()


@router.get("/news")
def list_news(limit: int = 40, db: Session = Depends(get_db)):
    news = db.query(NewsItem).order_by(NewsItem.published_at.desc()).limit(limit).all()
    return [
        {
            "symbol": n.symbol,
            "headline": n.headline,
            "url": n.url,
            "source": n.source,
            "published_at": n.published_at.isoformat(),
        }
        for n in news
    ]


@router.get("/global-news")
def list_global_news(min_impact: int = 0, limit: int = 40, db: Session = Depends(get_db)):
    news = (
        db.query(GlobalNewsItem)
        .filter(GlobalNewsItem.impact_score >= min_impact)
        .order_by(GlobalNewsItem.impact_score.desc(), GlobalNewsItem.published_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "category": n.category,
            "headline": n.headline,
            "summary": n.summary,
            "url": n.url,
            "source": n.source,
            "impact_score": n.impact_score,
            "published_at": n.published_at.isoformat(),
        }
        for n in news
    ]


@router.get("/economic-events")
def list_economic_events(days_ahead: int = 7, limit: int = 50, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    events = (
        db.query(EconomicEvent)
        .filter(EconomicEvent.event_date >= now - timedelta(days=1))
        .filter(EconomicEvent.event_date <= now + timedelta(days=days_ahead))
        .order_by(EconomicEvent.event_date)
        .limit(limit)
        .all()
    )
    return [
        {
            "event_name": e.event_name,
            "country": e.country,
            "event_date": e.event_date.isoformat(),
            "impact": e.impact,
            "forecast": e.forecast,
            "previous": e.previous,
        }
        for e in events
    ]


@router.get("/earnings-events")
def list_earnings_events(days_ahead: int = 7, limit: int = 50, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    events = (
        db.query(EarningsEvent)
        .filter(EarningsEvent.event_date >= now - timedelta(days=1))
        .filter(EarningsEvent.event_date <= now + timedelta(days=days_ahead))
        .order_by(EarningsEvent.event_date)
        .limit(limit)
        .all()
    )
    return [
        {
            "symbol": e.symbol,
            "event_date": e.event_date.isoformat(),
            "eps_estimate": e.eps_estimate,
            "revenue_estimate": e.revenue_estimate,
        }
        for e in events
    ]


@router.get("/dashboard-summary")
def dashboard_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace = get_or_create_workspace(db, user)
    items = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.active.is_(True))
        .all()
    )
    items = [
        item
        for item in items
        if (
            getattr(user, "is_admin", False)
            or item.user_id in (None, getattr(user, "id", None))
            or item.workspace_id in (None, workspace.id)
        )
    ]
    rows = []
    for item in items:
        snap = (
            db.query(PriceSnapshot)
            .filter(PriceSnapshot.watchlist_item_id == item.id)
            .order_by(PriceSnapshot.taken_at.desc())
            .first()
        )
        rows.append(
            {
                "id": item.id,
                "symbol": item.symbol,
                "label": item.label,
                "price": snap.price if snap else None,
                "change_pct": snap.change_pct if snap else None,
                "taken_at": snap.taken_at.isoformat() if snap else None,
            }
        )

    alerts = (
        db.query(AlertLog)
        .filter((AlertLog.user_id == user.id) | (AlertLog.user_id.is_(None)))
        .order_by(AlertLog.triggered_at.desc())
        .limit(20)
        .all()
    )
    alerts_out = [
        {
            "symbol": a.symbol,
            "message": a.message,
            "triggered_at": a.triggered_at.isoformat(),
            "delivered_telegram": a.delivered_telegram,
        }
        for a in alerts
    ]

    return {"rows": rows, "alerts": alerts_out}
