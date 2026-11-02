"""Historical OHLCV data via yfinance (no API key required).

Used to build the price/volume history needed to compute technical
indicators (RSI, MACD, moving averages, volume averages). Finnhub's free
tier does not include historical candles for US equities, so this fills
that gap at no cost.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


_COLUMNS = ["open", "high", "low", "close", "volume"]
PROVIDER_NAME = "yfinance"
PROVIDER_ROLE = "historical_ohlcv"
REQUIRED_FOR_TECHNICAL_ANALYSIS = True

_CACHE_DIR = Path(os.getenv("YFINANCE_CACHE_DIR", "data/yfinance_cache"))
try:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(_CACHE_DIR))
except Exception:
    logger.warning("Nao foi possivel configurar o cache local do yfinance.", exc_info=True)


@dataclass
class FxQuote:
    pair: str
    rate: float
    change_pct: float
    updated_at: datetime


@dataclass
class CommodityQuote:
    symbol: str
    name: str
    unit: str
    price: float
    change_pct: float
    updated_at: datetime


@dataclass
class IndexQuote:
    symbol: str
    name: str
    price: float
    change_pct: float
    day_high: float
    day_low: float
    prev_close: float
    updated_at: datetime


def get_history(symbol: str, period: str = "5d", interval: str = "15m") -> pd.DataFrame:
    """Returns a DataFrame with columns [open, high, low, close, volume], indexed by
    datetime (ascending). open/high/low are used for the candlestick chart; close/volume
    are what the indicators and rules engine consume.
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=True)
    except Exception:
        logger.exception("Falha ao buscar histórico de %s no yfinance", symbol)
        return pd.DataFrame(columns=_COLUMNS)

    if df.empty:
        return pd.DataFrame(columns=_COLUMNS)

    out = df.rename(
        columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    )[_COLUMNS]
    out.index.name = "timestamp"
    return out


def get_usd_brl_quote() -> FxQuote | None:
    """Returns the USD/BRL exchange rate from Yahoo Finance's BRL=X ticker."""
    history = get_history("BRL=X", period="5d", interval="1d")
    if history.empty:
        return None

    close = history["close"].dropna()
    if close.empty:
        return None

    latest = float(close.iloc[-1])
    previous = float(close.iloc[-2]) if len(close) >= 2 else latest
    change_pct = ((latest - previous) / previous * 100) if previous else 0.0
    timestamp = close.index[-1]
    if hasattr(timestamp, "to_pydatetime"):
        updated_at = timestamp.to_pydatetime()
    else:
        updated_at = datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    return FxQuote(pair="USD/BRL", rate=latest, change_pct=change_pct, updated_at=updated_at)


def _as_updated_at(timestamp) -> datetime:
    if hasattr(timestamp, "to_pydatetime"):
        updated_at = timestamp.to_pydatetime()
    else:
        updated_at = datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return updated_at


def get_commodity_quote(symbol: str, name: str, unit: str) -> CommodityQuote | None:
    """Returns a daily commodity/futures quote (e.g. GC=F for gold)."""
    history = get_history(symbol, period="5d", interval="1d")
    if history.empty:
        return None

    close = history["close"].dropna()
    if close.empty:
        return None

    latest = float(close.iloc[-1])
    previous = float(close.iloc[-2]) if len(close) >= 2 else latest
    change_pct = ((latest - previous) / previous * 100) if previous else 0.0

    return CommodityQuote(
        symbol=symbol,
        name=name,
        unit=unit,
        price=latest,
        change_pct=change_pct,
        updated_at=_as_updated_at(close.index[-1]),
    )


def get_gold_quote() -> CommodityQuote | None:
    """Returns the gold futures price (GC=F), quoted in USD per troy ounce."""
    return get_commodity_quote("GC=F", "Ouro", "onca troy")


def get_index_quote(symbol: str, name: str) -> IndexQuote | None:
    """Returns a daily quote (price, change, day range) for an index/future ticker.

    Used for pre-market/morning analysis of broad indices (Nasdaq, S&P/NYSE) — these
    aren't part of the equities watchlist, so they don't get PriceSnapshot rows from
    Finnhub and need their own lightweight fetch via yfinance.
    """
    history = get_history(symbol, period="5d", interval="1d")
    if history.empty:
        return None

    close = history["close"].dropna()
    if close.empty:
        return None

    latest = float(close.iloc[-1])
    previous = float(close.iloc[-2]) if len(close) >= 2 else latest
    change_pct = ((latest - previous) / previous * 100) if previous else 0.0
    last_row = history.iloc[-1]

    return IndexQuote(
        symbol=symbol,
        name=name,
        price=latest,
        change_pct=change_pct,
        day_high=float(last_row["high"]),
        day_low=float(last_row["low"]),
        prev_close=previous,
        updated_at=_as_updated_at(close.index[-1]),
    )


NASDAQ_FUTURES_SYMBOL = "NQ=F"
SP500_FUTURES_SYMBOL = "ES=F"


def get_nasdaq_quote() -> IndexQuote | None:
    """Nasdaq-100 futures (NQ=F) — proxy for the Nasdaq market referenced in the morning report."""
    return get_index_quote(NASDAQ_FUTURES_SYMBOL, "Nasdaq-100 (futuro)")


def get_sp500_quote() -> IndexQuote | None:
    """S&P500 futures (ES=F) — proxy for the broad NYSE/American market."""
    return get_index_quote(SP500_FUTURES_SYMBOL, "S&P500 (futuro)")


# The macro/cross-asset instrument registry (NASDAQ, DXY, Treasury yields,
# etc.) now lives in app.market_data.macro_data — it routes each instrument
# to its most reliable source (FRED for yields/dollar index, yfinance for
# everything else) instead of only ever using Yahoo proxies.
def get_quote(symbol: str):
    """Cotação via yfinance (sem chave) — fallback quando o Finnhub não está configurado."""
    from app.market_data.finnhub_client import Quote

    history = get_history(symbol, period="5d", interval="1d")
    close = history["close"].dropna() if not history.empty else history
    if len(close) == 0:
        return None
    latest = float(close.iloc[-1])
    previous = float(close.iloc[-2]) if len(close) >= 2 else latest
    change_pct = ((latest - previous) / previous * 100) if previous else 0.0
    volume = float(history["volume"].iloc[-1]) if "volume" in history and len(history) else 0.0
    return Quote(symbol=symbol, price=latest, change_pct=change_pct, volume=volume)
