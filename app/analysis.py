"""Análise técnica e pacote de exportação (JSON/CSV) com números concretos.

Tudo descritivo ("RSI 72 = região de sobrecompra"), nunca recomendação de compra/venda —
mesma regra do copiloto/LLM do projeto.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy.orm import Session

from app import indicators
from app.market_data import yfinance_client
from app.scope import active_watchlist
from app.models import EarningsEvent, EconomicEvent, GlobalNewsItem, NewsItem, PriceSnapshot, WatchlistItem


def _last(series: pd.Series, decimals: int = 2) -> float | None:
    clean = series.dropna()
    return round(float(clean.iloc[-1]), decimals) if len(clean) else None


def technical_snapshot(symbol: str, history: pd.DataFrame | None = None) -> dict | None:
    """Indicadores atuais de um ativo a partir do histórico diário (6 meses)."""
    if history is None:
        history = yfinance_client.get_history(symbol, period="6mo", interval="1d")
    if history.empty or len(history) < 2:
        return None

    close = history["close"]
    price = _last(close)
    rsi = _last(indicators.rsi(close))
    macd_df = indicators.macd(close)
    macd_hist = _last(macd_df["histogram"], 3)
    ema_fast, ema_slow = _last(indicators.ema(close, 9)), _last(indicators.ema(close, 21))
    sma50 = _last(indicators.sma(close, 50))
    bb = indicators.bollinger_bands(close)
    bb_upper, bb_lower = _last(bb["upper"]), _last(bb["lower"])
    vol_ratio = _last(indicators.volume_ratio(history["volume"].astype(float)))
    change_1d = _last(indicators.pct_change_over_window(close, 1))
    change_5d = _last(indicators.pct_change_over_window(close, 5))
    change_1m = _last(indicators.pct_change_over_window(close, 21))

    prior = history.iloc[-2]
    pivots = indicators.classic_pivot_points(float(prior["high"]), float(prior["low"]), float(prior["close"]))
    swings = indicators.swing_levels(history, lookback=20)

    notes = []
    if rsi is not None:
        if rsi >= 70:
            notes.append(f"RSI {rsi} em região de sobrecompra (>=70)")
        elif rsi <= 30:
            notes.append(f"RSI {rsi} em região de sobrevenda (<=30)")
        else:
            notes.append(f"RSI {rsi} neutro")
    if ema_fast is not None and ema_slow is not None:
        notes.append(
            "EMA9 acima da EMA21 (tendência de curto prazo de alta)"
            if ema_fast > ema_slow
            else "EMA9 abaixo da EMA21 (tendência de curto prazo de baixa)"
        )
    if macd_hist is not None:
        notes.append("MACD com histograma positivo" if macd_hist > 0 else "MACD com histograma negativo")
    if price is not None and sma50 is not None:
        notes.append(f"Preço {'acima' if price > sma50 else 'abaixo'} da SMA50 ({sma50})")
    if price is not None and bb_upper is not None and price >= bb_upper:
        notes.append("Preço tocando/acima da banda superior de Bollinger")
    if price is not None and bb_lower is not None and price <= bb_lower:
        notes.append("Preço tocando/abaixo da banda inferior de Bollinger")
    if vol_ratio is not None and vol_ratio >= 1.5:
        notes.append(f"Volume {vol_ratio}x acima da média de 20 dias")

    return {
        "symbol": symbol,
        "price": price,
        "change_1d_pct": change_1d,
        "change_5d_pct": change_5d,
        "change_1m_pct": change_1m,
        "rsi14": rsi,
        "macd_histogram": macd_hist,
        "ema9": ema_fast,
        "ema21": ema_slow,
        "sma50": sma50,
        "bollinger_upper": bb_upper,
        "bollinger_lower": bb_lower,
        "volume_ratio_20d": vol_ratio,
        "pivot": pivots["pivot"],
        "r1": pivots["r1"],
        "r2": pivots["r2"],
        "s1": pivots["s1"],
        "s2": pivots["s2"],
        "swing_high_20d": swings["swing_high"],
        "swing_low_20d": swings["swing_low"],
        "notes": notes,
    }


def build_export(db: Session, news_limit: int = 50, user_id: int | None = None) -> dict:
    """Pacote completo: análise técnica por ativo + notícias + calendários."""
    now = datetime.now(timezone.utc)
    items = active_watchlist(db, user_id)

    analysis = []
    for item in items:
        snap = (
            db.query(PriceSnapshot)
            .filter(PriceSnapshot.watchlist_item_id == item.id)
            .order_by(PriceSnapshot.taken_at.desc())
            .first()
        )
        tech = technical_snapshot(item.symbol) or {"symbol": item.symbol, "notes": ["sem histórico disponível"]}
        if snap:
            tech["last_snapshot_price"] = round(snap.price, 2)
            tech["last_snapshot_at"] = snap.taken_at.isoformat()
        analysis.append(tech)

    asset_news = db.query(NewsItem).order_by(NewsItem.published_at.desc()).limit(news_limit).all()
    global_news = (
        db.query(GlobalNewsItem)
        .order_by(GlobalNewsItem.published_at.desc(), GlobalNewsItem.impact_score.desc())
        .limit(news_limit)
        .all()
    )
    econ = (
        db.query(EconomicEvent)
        .filter(EconomicEvent.event_date >= now, EconomicEvent.event_date <= now + timedelta(days=14))
        .order_by(EconomicEvent.event_date)
        .all()
    )
    earnings = (
        db.query(EarningsEvent)
        .filter(EarningsEvent.event_date >= now, EarningsEvent.event_date <= now + timedelta(days=14))
        .order_by(EarningsEvent.event_date)
        .all()
    )

    return {
        "generated_at": now.isoformat(),
        "disclaimer": "Dados descritivos; não é recomendação de investimento. Podem ter atraso.",
        "analysis": analysis,
        "news_by_asset": [
            {
                "symbol": n.symbol,
                "published_at": n.published_at.isoformat(),
                "headline": n.headline,
                "source": n.source,
                "url": n.url,
            }
            for n in asset_news
        ],
        "global_news": [
            {
                "category": n.category,
                "published_at": n.published_at.isoformat(),
                "impact_score": n.impact_score,
                "headline": n.headline,
                "source": n.source,
                "url": n.url,
            }
            for n in global_news
        ],
        "economic_events": [
            {
                "date": e.event_date.isoformat(),
                "event": e.event_name,
                "country": e.country,
                "impact": e.impact,
                "forecast": e.forecast,
                "previous": e.previous,
            }
            for e in econ
        ],
        "earnings": [
            {
                "symbol": e.symbol,
                "date": e.event_date.date().isoformat(),
                "eps_estimate": e.eps_estimate,
                "revenue_estimate": e.revenue_estimate,
            }
            for e in earnings
        ],
    }


def export_csv(data: dict) -> str:
    """CSV único com seções (abre direto no Excel/Sheets)."""
    out = io.StringIO()
    w = csv.writer(out)

    def section(title: str, rows: list[dict], columns: list[str]):
        w.writerow([f"# {title}"])
        w.writerow(columns)
        for r in rows:
            w.writerow([" | ".join(v) if isinstance(v, list) else v for v in (r.get(c, "") for c in columns)])
        w.writerow([])

    w.writerow(["# Monitor NASDAQ", data["generated_at"]])
    w.writerow([data["disclaimer"]])
    w.writerow([])
    section(
        "Análise técnica",
        data["analysis"],
        ["symbol", "price", "change_1d_pct", "change_5d_pct", "change_1m_pct", "rsi14", "macd_histogram", "ema9",
         "ema21", "sma50", "bollinger_upper", "bollinger_lower", "volume_ratio_20d", "pivot", "r1", "r2", "s1", "s2",
         "swing_high_20d", "swing_low_20d", "notes"],
    )
    section("Notícias globais", data["global_news"], ["published_at", "category", "impact_score", "headline", "source", "url"])
    section("Notícias por ativo", data["news_by_asset"], ["published_at", "symbol", "headline", "source", "url"])
    section("Calendário econômico", data["economic_events"], ["date", "event", "country", "impact", "forecast", "previous"])
    section("Earnings", data["earnings"], ["date", "symbol", "eps_estimate", "revenue_estimate"])
    return out.getvalue()
