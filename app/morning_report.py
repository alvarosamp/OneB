"""Builds the daily pre-market briefing ("análise matinal"): the same kind of
morning market read a trading desk does by hand — index levels, support/
resistance, overnight news and today's calendar — but computed from the data
this app already collects, and reproducible every morning without a human
manually redrawing lines on a chart.

Levels are classic pivot points (P, S1-S3, R1-R3) off the prior day's OHLC,
plus the recent swing high/low — a standard, well-defined substitute for a
discretionary hand-drawn trendline.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app import indicators
from app.config import settings
from app.market_data import yfinance_client
from app.scope import active_watchlist, latest_snapshot
from app.models import EarningsEvent, EconomicEvent, GlobalNewsItem, MorningReport, PriceSnapshot, WatchlistItem

INDEX_FETCHERS = [
    ("nasdaq", "get_nasdaq_quote"),
    ("sp500_nyse", "get_sp500_quote"),
    ("gold", "get_gold_quote"),
]


def _quote_levels(symbol: str) -> dict | None:
    """Daily history for `symbol` -> pivot points (prior day OHLC) + swing levels."""
    history = yfinance_client.get_history(symbol, period="3mo", interval="1d")
    if history.empty or len(history) < 2:
        return None
    prior = history.iloc[-2]
    pivots = indicators.classic_pivot_points(float(prior["high"]), float(prior["low"]), float(prior["close"]))
    swings = indicators.swing_levels(history, lookback=20)
    return {"pivots": pivots, **swings}


def _index_section(key: str, fetcher_name: str) -> dict | None:
    quote = getattr(yfinance_client, fetcher_name)()
    if quote is None:
        return None
    levels = _quote_levels(quote.symbol)
    return {
        "key": key,
        "symbol": quote.symbol,
        "name": quote.name,
        "price": round(quote.price, 2),
        "change_pct": round(quote.change_pct, 2),
        "levels": levels,
    }


MAX_WATCHLIST_IN_REPORT = 10  # cada ativo custa uma chamada ao yfinance para os pivôs


def watchlist_section(db: Session, user_id: int) -> list[dict]:
    out = []
    for item in active_watchlist(db, user_id)[:MAX_WATCHLIST_IN_REPORT]:
        snap = latest_snapshot(db, item.id)
        levels = _quote_levels(item.symbol)
        out.append(
            {
                "symbol": item.symbol,
                "price": round(snap.price, 2) if snap else None,
                "change_pct": round(snap.change_pct, 2) if snap else None,
                "levels": levels,
            }
        )
    return out


def build_report_data(db: Session) -> dict:
    """Dados do relatório matinal de mercado, iguais para todos (índices, notícias, calendário).

    A watchlist de cada usuário entra só na hora da leitura (`watchlist_section`), nunca no
    relatório guardado.
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=16)  # covers the prior US close through this morning
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    indices = [section for key, fetcher_name in INDEX_FETCHERS if (section := _index_section(key, fetcher_name))]
    watchlist: list[dict] = []

    overnight_news = (
        db.query(GlobalNewsItem)
        .filter(GlobalNewsItem.published_at >= since)
        .order_by(GlobalNewsItem.impact_score.desc(), GlobalNewsItem.published_at.desc())
        .limit(8)
        .all()
    )
    econ_today = (
        db.query(EconomicEvent)
        .filter(
            EconomicEvent.event_date >= today_start,
            EconomicEvent.event_date < today_end,
            EconomicEvent.impact == "high",
        )
        .order_by(EconomicEvent.event_date)
        .all()
    )
    earnings_today = (
        db.query(EarningsEvent)
        .filter(EarningsEvent.event_date >= today_start, EarningsEvent.event_date < today_end)
        .all()
    )

    return {
        "date": date.today().isoformat(),
        "indices": indices,
        "watchlist": watchlist,
        "overnight_news": [
            {"headline": n.headline, "source": n.source, "impact_score": n.impact_score} for n in overnight_news
        ],
        "economic_events_today": [{"event_name": e.event_name, "country": e.country} for e in econ_today],
        "earnings_today": [e.symbol for e in earnings_today],
    }


def _fmt_levels(levels: dict | None) -> str:
    if not levels:
        return "sem historico suficiente para niveis"
    p = levels["pivots"]
    return f"P {p['pivot']} | R1 {p['r1']} / R2 {p['r2']} | S1 {p['s1']} / S2 {p['s2']}"


def render_text(data: dict) -> str:
    """Deterministic, non-LLM rendering of the report — used as the Telegram/
    fallback message when the LLM narrative is disabled or unavailable.
    """
    lines = [f"Analise matinal - {data['date']}"]

    if data["indices"]:
        lines.append("\nIndices:")
        for idx in data["indices"]:
            arrow = "🔺" if idx["change_pct"] >= 0 else "🔻"
            lines.append(f"• {idx['name']}: {idx['price']} {arrow} {idx['change_pct']:+.2f}%")
            lines.append(f"  niveis: {_fmt_levels(idx['levels'])}")

    if data["watchlist"]:
        lines.append("\nWatchlist:")
        for w in data["watchlist"]:
            if w["price"] is None:
                lines.append(f"• {w['symbol']}: sem dados ainda")
                continue
            arrow = "🔺" if (w["change_pct"] or 0) >= 0 else "🔻"
            lines.append(f"• {w['symbol']}: {w['price']} {arrow} {w['change_pct']:+.2f}%")
            lines.append(f"  niveis: {_fmt_levels(w['levels'])}")

    if data["overnight_news"]:
        lines.append("\nNoticias de maior impacto (ultimas horas):")
        lines.extend(f"• {n['headline']} ({n['source'] or 'fonte desconhecida'})" for n in data["overnight_news"][:5])

    if data["economic_events_today"]:
        lines.append("\nEventos economicos de alto impacto hoje:")
        lines.extend(f"• {e['event_name']} ({e['country']})" for e in data["economic_events_today"])

    if data["earnings_today"]:
        lines.append("\nEarnings hoje: " + ", ".join(data["earnings_today"]))

    return "\n".join(lines)


async def generate_and_store(db: Session) -> MorningReport:
    """Builds the report, optionally enriches it with an LLM narrative, and
    persists it so the dashboard/history can show it without recomputing.
    """
    data = build_report_data(db)
    narrative = render_text(data)

    if settings.llm_daily_narrative_enabled:
        from app.llm_client import generate_morning_narrative

        generated = await generate_morning_narrative(data)
        if generated:
            narrative = generated

    report = MorningReport(narrative=narrative, data=data)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
