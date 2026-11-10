"""Tiingo EOD price client.

Tiingo is useful here as a research-grade replacement for yfinance daily
history: it exposes raw and adjusted OHLCV plus split/dividend fields, and
documents an EOD correction workflow. We use adjusted OHLCV by default so
technical features stay comparable through splits and dividends.
"""
from __future__ import annotations

import logging
from datetime import date

import httpx
import pandas as pd

from app.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.tiingo.com/tiingo/daily"
PROVIDER_NAME = "tiingo"
PROVIDER_ROLE = "Primary EOD OHLCV provider for adjusted daily candles, indicators and backtests."
_COLUMNS = ["open", "high", "low", "close", "volume"]


def _start_date_for_period(period: str) -> date | None:
    period = (period or "").strip().lower()
    if period in {"max", "full"}:
        return None
    now = pd.Timestamp.utcnow().normalize()
    if period.endswith("y") and period[:-1].isdigit():
        return (now - pd.DateOffset(years=int(period[:-1]))).date()
    if period.endswith("mo") and period[:-2].isdigit():
        return (now - pd.DateOffset(months=int(period[:-2]))).date()
    if period.endswith("d") and period[:-1].isdigit():
        return (now - pd.Timedelta(days=int(period[:-1]))).date()
    return (now - pd.DateOffset(years=1)).date()


def get_history(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    if interval != "1d":
        logger.warning("Tiingo EOD suporta apenas interval=1d; recebido %s para %s.", interval, symbol)
        return pd.DataFrame(columns=_COLUMNS)
    if not settings.tiingo_api_key:
        logger.warning("TIINGO_API_KEY nao configurada; historico Tiingo indisponivel.")
        return pd.DataFrame(columns=_COLUMNS)

    start_date = _start_date_for_period(period)
    params = {}
    if start_date is not None:
        params["startDate"] = start_date.isoformat()

    try:
        headers = {"Content-Type": "application/json", "Authorization": f"Token {settings.tiingo_api_key}"}
        response = httpx.get(f"{BASE_URL}/{symbol.lower()}/prices", params=params, headers=headers, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        logger.exception("Falha ao buscar historico de %s no Tiingo", symbol)
        return pd.DataFrame(columns=_COLUMNS)

    if not isinstance(payload, list) or not payload:
        return pd.DataFrame(columns=_COLUMNS)

    raw = pd.DataFrame(payload)
    required = {"date", "adjOpen", "adjHigh", "adjLow", "adjClose", "adjVolume"}
    if not required.issubset(raw.columns):
        logger.warning("Resposta Tiingo de %s sem colunas ajustadas esperadas.", symbol)
        return pd.DataFrame(columns=_COLUMNS)

    out = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(raw["date"], errors="coerce"),
            "open": pd.to_numeric(raw["adjOpen"], errors="coerce"),
            "high": pd.to_numeric(raw["adjHigh"], errors="coerce"),
            "low": pd.to_numeric(raw["adjLow"], errors="coerce"),
            "close": pd.to_numeric(raw["adjClose"], errors="coerce"),
            "volume": pd.to_numeric(raw["adjVolume"], errors="coerce"),
        }
    ).dropna(subset=["timestamp", "open", "high", "low", "close"])
    if out.empty:
        return pd.DataFrame(columns=_COLUMNS)
    out = out.set_index("timestamp").sort_index()
    out.index.name = "timestamp"
    return out[_COLUMNS]
