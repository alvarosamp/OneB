from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

import pandas as pd

from app.config import settings
from app.market_data import tiingo_client, yfinance_client


@dataclass(frozen=True)
class MarketQuote:
    symbol: str
    price: float
    change_pct: float
    provider: str
    provider_time: datetime
    received_at: datetime


class MarketDataProvider(Protocol):
    name: str

    def get_bars(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        ...

    def get_quote(self, symbol: str) -> MarketQuote | None:
        ...


class YahooMarketDataProvider:
    name = "yfinance"

    def get_bars(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        return yfinance_client.get_history(symbol, period=period, interval=interval)

    def get_quote(self, symbol: str) -> MarketQuote | None:
        history = self.get_bars(symbol, period="5d", interval="1d")
        if history.empty:
            return None
        close = history["close"].dropna()
        if close.empty:
            return None
        latest = float(close.iloc[-1])
        previous = float(close.iloc[-2]) if len(close) >= 2 else latest
        change_pct = ((latest - previous) / previous * 100) if previous else 0.0
        ts = close.index[-1]
        provider_time = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else datetime.now(timezone.utc)
        if provider_time.tzinfo is None:
            provider_time = provider_time.replace(tzinfo=timezone.utc)
        return MarketQuote(
            symbol=symbol.upper(),
            price=latest,
            change_pct=change_pct,
            provider=self.name,
            provider_time=provider_time,
            received_at=datetime.now(timezone.utc),
        )


class TiingoMarketDataProvider:
    name = "tiingo"

    def get_bars(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        return tiingo_client.get_history(symbol, period=period, interval=interval)

    def get_quote(self, symbol: str) -> MarketQuote | None:
        history = self.get_bars(symbol, period="5d", interval="1d")
        if history.empty:
            return None
        close = history["close"].dropna()
        if close.empty:
            return None
        latest = float(close.iloc[-1])
        previous = float(close.iloc[-2]) if len(close) >= 2 else latest
        change_pct = ((latest - previous) / previous * 100) if previous else 0.0
        ts = close.index[-1]
        provider_time = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else datetime.now(timezone.utc)
        if provider_time.tzinfo is None:
            provider_time = provider_time.replace(tzinfo=timezone.utc)
        return MarketQuote(
            symbol=symbol.upper(),
            price=latest,
            change_pct=change_pct,
            provider=self.name,
            provider_time=provider_time,
            received_at=datetime.now(timezone.utc),
        )


def _default_provider() -> MarketDataProvider:
    provider = settings.market_data_provider.strip().lower()
    if provider == "tiingo":
        return TiingoMarketDataProvider()
    return YahooMarketDataProvider()


default_provider: MarketDataProvider = _default_provider()


def get_bars(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    from app.market_data.service import get_bars as service_get_bars

    return service_get_bars(symbol, period=period, interval=interval)


def get_quote(symbol: str) -> MarketQuote | None:
    from app.market_data.service import get_quote as service_get_quote

    return service_get_quote(symbol)
