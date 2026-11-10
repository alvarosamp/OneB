"""Thin client for Financial Modeling Prep's fundamentals (annual key
metrics / income statement).

Free tier account required at https://financialmodelingprep.com (separate
API key from Finnhub).

NOTE: this module used to also provide the economic calendar, but FMP
retired the whole /api/v3 surface on 2025-08-31 and the /stable
replacement (economic-calendar) returned 402 "Restricted Endpoint" on this
account's free-tier key — confirmed during this session's data audit. The
economic calendar now comes from app.market_data.fred_client.get_economic_calendar
instead (FRED's own release-dates endpoint, same key already in use for
macro series, no separate signup).
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

STABLE_BASE_URL = "https://financialmodelingprep.com/stable"
MAX_FREE_TIER_LIMIT = 5


def _get_stable(endpoint: str, symbol: str, limit: int = MAX_FREE_TIER_LIMIT) -> list[dict]:
    """Shared fetch for the annual-only /stable fundamentals endpoints.
    `limit` is capped at MAX_FREE_TIER_LIMIT — the free plan 402s above 5.
    """
    if not settings.fmp_api_key:
        logger.warning("FMP_API_KEY não configurada — fundamentals (%s) indisponível.", endpoint)
        return []

    try:
        resp = httpx.get(
            f"{STABLE_BASE_URL}/{endpoint}",
            params={"symbol": symbol, "limit": min(limit, MAX_FREE_TIER_LIMIT), "apikey": settings.fmp_api_key},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.exception("Falha ao buscar %s para %s na FMP", endpoint, symbol)
        return []

    return data if isinstance(data, list) else []


def get_key_metrics(symbol: str, limit: int = MAX_FREE_TIER_LIMIT) -> list[dict]:
    """Up to 5 most recent annual key-metrics reports (valuation, returns,
    leverage ratios), newest first. Each row has a "date" (fiscal period
    end) but NOT a filing date — join with get_income_statement on "date"
    to get filingDate for point-in-time-correct usage.
    """
    return _get_stable("key-metrics", symbol, limit)


def get_income_statement(symbol: str, limit: int = MAX_FREE_TIER_LIMIT) -> list[dict]:
    """Up to 5 most recent annual income statements, newest first. Includes
    "filingDate" — the date this report actually became public, which is
    what any point-in-time feature join must use instead of "date" (period
    end) to avoid look-ahead bias.
    """
    return _get_stable("income-statement", symbol, limit)
