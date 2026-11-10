"""Thin wrapper around the Finnhub REST API for real-time-ish quotes.

Free tier: 60 API calls/minute. We only use the lightweight /quote endpoint
here, polled on a schedule (see app.scheduler), which is well within limits
for a small watchlist.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone

import finnhub

from app.config import settings

logger = logging.getLogger(__name__)

_client: finnhub.Client | None = None


def get_client() -> finnhub.Client:
    global _client
    if _client is None:
        if not settings.finnhub_api_key:
            raise RuntimeError("FINNHUB_API_KEY não configurada no .env")
        _client = finnhub.Client(api_key=settings.finnhub_api_key)
    return _client


@dataclass
class Quote:
    symbol: str
    price: float
    change_pct: float
    volume: float = 0.0


def get_quote(symbol: str) -> Quote | None:
    try:
        client = get_client()
        data = client.quote(symbol)
    except Exception:
        logger.exception("Falha ao buscar cotação de %s no Finnhub", symbol)
        return None

    current = data.get("c") or 0.0
    prev_close = data.get("pc") or 0.0
    if not current:
        return None

    change_pct = ((current - prev_close) / prev_close * 100) if prev_close else 0.0
    return Quote(symbol=symbol, price=float(current), change_pct=float(change_pct))


@dataclass
class NewsArticle:
    symbol: str
    headline: str
    summary: str
    url: str
    source: str
    published_at: datetime


_HIGH_IMPACT_TERMS = {
    "fed",
    "powell",
    "fomc",
    "rate",
    "rates",
    "interest",
    "inflation",
    "cpi",
    "ppi",
    "jobs",
    "payroll",
    "recession",
    "tariff",
    "tariffs",
    "war",
    "attack",
    "sanction",
    "sanctions",
    "oil",
    "treasury",
    "yields",
    "bank",
    "banks",
    "default",
    "shutdown",
    "guidance",
    "earnings",
    "ai",
    "chips",
    "semiconductor",
}

_MEDIUM_IMPACT_TERMS = {
    "dollar",
    "nasdaq",
    "s&p",
    "sp500",
    "dow",
    "futures",
    "growth",
    "china",
    "europe",
    "consumer",
    "retail",
    "housing",
    "manufacturing",
    "debt",
}


def estimate_news_impact(headline: str, summary: str = "") -> int:
    text = f"{headline} {summary}".lower()
    score = 0
    score += sum(18 for term in _HIGH_IMPACT_TERMS if term in text)
    score += sum(8 for term in _MEDIUM_IMPACT_TERMS if term in text)
    return min(score, 100)


def get_company_news(symbol: str, from_date: date, to_date: date) -> list[NewsArticle]:
    try:
        client = get_client()
        data = client.company_news(symbol, _from=from_date.isoformat(), to=to_date.isoformat())
    except Exception:
        logger.exception("Falha ao buscar notícias de %s no Finnhub", symbol)
        return []

    articles = []
    for item in data or []:
        url = item.get("url")
        headline = item.get("headline")
        if not url or not headline:
            continue
        ts = item.get("datetime")
        published_at = (
            datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc)
        )
        articles.append(
            NewsArticle(
                symbol=symbol,
                headline=headline,
                summary=item.get("summary", ""),
                url=url,
                source=item.get("source", ""),
                published_at=published_at,
            )
        )
    return articles


def get_market_news(category: str = "general", limit: int = 30) -> list[NewsArticle]:
    try:
        client = get_client()
        data = client.general_news(category, min_id=0)
    except Exception:
        logger.exception("Falha ao buscar noticias globais no Finnhub (%s)", category)
        return []

    articles = []
    for item in (data or [])[:limit]:
        url = item.get("url")
        headline = item.get("headline")
        if not url or not headline:
            continue
        ts = item.get("datetime")
        published_at = (
            datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc)
        )
        articles.append(
            NewsArticle(
                symbol=category.upper(),
                headline=headline,
                summary=item.get("summary", ""),
                url=url,
                source=item.get("source", ""),
                published_at=published_at,
            )
        )
    return articles


@dataclass
class EarningsEntry:
    symbol: str
    event_date: datetime
    eps_estimate: float | None
    revenue_estimate: float | None


def get_earnings_calendar(from_date: date, to_date: date, symbol: str | None = None) -> list[EarningsEntry]:
    try:
        client = get_client()
        # finnhub-python's earnings_calendar() takes `symbol` as a required
        # positional/keyword argument (no default) — omitting it raises
        # TypeError, not an empty result. "" is the library's own documented
        # way to ask for the global calendar (all symbols).
        data = client.earnings_calendar(_from=from_date.isoformat(), to=to_date.isoformat(), symbol=symbol or "")
    except Exception:
        logger.exception("Falha ao buscar calendário de earnings no Finnhub")
        return []

    entries = []
    for item in (data or {}).get("earningsCalendar", []):
        sym = item.get("symbol")
        raw_date = item.get("date")
        if not sym or not raw_date:
            continue
        try:
            event_date = datetime.fromisoformat(raw_date).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        entries.append(
            EarningsEntry(
                symbol=sym,
                event_date=event_date,
                eps_estimate=item.get("epsEstimate"),
                revenue_estimate=item.get("revenueEstimate"),
            )
        )
    return entries
