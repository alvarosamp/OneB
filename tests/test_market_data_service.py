from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd

from app.market_data import macro_data
from app.market_data.providers import MarketQuote
from app.market_data.service import MarketDataService, normalize_bars


class FakeProvider:
    name = "fake"

    def __init__(self):
        self.calls = 0

    def get_bars(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        self.calls += 1
        dates = pd.date_range("2026-01-01", periods=3, freq="D", tz="UTC")
        return pd.DataFrame(
            {
                "Open": [10, 11, 12],
                "High": [11, 12, 13],
                "Low": [9, 10, 11],
                "Close": [10.5, 11.5, 12.5],
                "Volume": [1000, 1100, 1200],
            },
            index=dates,
        )

    def get_quote(self, symbol: str) -> MarketQuote | None:
        return MarketQuote(
            symbol=symbol.upper(),
            price=12.5,
            change_pct=1.0,
            provider=self.name,
            provider_time=datetime(2026, 1, 3, tzinfo=timezone.utc),
            received_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
        )


class EmptyProvider:
    name = "empty"

    def __init__(self):
        self.calls = 0

    def get_bars(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        self.calls += 1
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    def get_quote(self, symbol: str) -> MarketQuote | None:
        return None


class ErrorProvider:
    name = "fake"

    def get_bars(self, *_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    def get_quote(self, _symbol: str) -> MarketQuote | None:
        return None


def test_normalize_bars_standardizes_columns_and_index():
    raw = pd.DataFrame(
        {"Open": [2], "High": [3], "Low": [1], "Close": [2.5], "Volume": [100]},
        index=["2026-01-02"],
    )

    bars, issues = normalize_bars(raw)

    assert issues == []
    assert list(bars.columns) == ["open", "high", "low", "close", "volume"]
    assert bars.index[0] == pd.Timestamp("2026-01-02")


def _workspace_tmp() -> Path:
    path = Path("tmp") / "market_data_service_tests" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_market_data_service_uses_cache_after_first_fetch():
    provider = FakeProvider()
    service = MarketDataService(provider=provider, data_root=_workspace_tmp())

    first = service.get_bars("AAPL", period="1y", interval="1d")
    second = service.get_bars("AAPL", period="1y", interval="1d")

    assert provider.calls == 1
    assert len(first) == 3
    assert second.equals(first)
    metadata = service.load_metadata("AAPL", interval="1d")
    assert metadata is not None
    assert metadata["symbol"] == "AAPL"
    assert metadata["provider"] == "fake"
    assert metadata["rows"] == 3


def test_market_data_service_refresh_bypasses_cache():
    provider = FakeProvider()
    service = MarketDataService(provider=provider, data_root=_workspace_tmp())

    service.get_bars("AAPL", period="1y", interval="1d")
    service.refresh_bars("AAPL", period="1y", interval="1d")

    assert provider.calls == 2


def test_market_data_service_cache_is_period_specific():
    provider = FakeProvider()
    service = MarketDataService(provider=provider, data_root=_workspace_tmp())

    service.get_bars("AAPL", period="5d", interval="1d")
    service.get_bars("AAPL", period="1y", interval="1d")

    assert provider.calls == 2


def test_macro_us10y_fallback_scales_tnx_proxy(monkeypatch):
    dates = pd.date_range("2026-01-01", periods=2, freq="D", tz="UTC")
    proxy = pd.DataFrame(
        {"open": [45.0, 46.0], "high": [45.2, 46.2], "low": [44.8, 45.8], "close": [45.1, 46.1], "volume": [0, 0]},
        index=dates,
    )

    monkeypatch.setattr(macro_data.fred_client, "get_series", lambda *_args, **_kwargs: pd.DataFrame())
    monkeypatch.setattr(macro_data.market_data_service, "get_bars", lambda *_args, **_kwargs: proxy)

    history = macro_data.get_macro_history("US10Y", period="5d", interval="1d")

    assert history["close"].iloc[-1] == 4.61


def test_macro_dxy_fallback_uses_yfinance_proxy(monkeypatch):
    dates = pd.date_range("2026-01-01", periods=2, freq="D", tz="UTC")
    proxy = pd.DataFrame(
        {"open": [100.0, 101.0], "high": [101.0, 102.0], "low": [99.0, 100.0], "close": [100.5, 101.5], "volume": [0, 0]},
        index=dates,
    )

    monkeypatch.setattr(macro_data.fred_client, "get_series", lambda *_args, **_kwargs: pd.DataFrame())
    monkeypatch.setattr(macro_data.market_data_service, "get_bars", lambda *_args, **_kwargs: proxy)

    history = macro_data.get_macro_history("DXY", period="5d", interval="1d")

    assert history.equals(proxy)


def test_market_data_service_cache_only_does_not_call_provider_without_cache():
    provider = FakeProvider()
    service = MarketDataService(provider=provider, data_root=_workspace_tmp())

    bars = service.get_bars("AAPL", period="1y", interval="1d", cache_only=True)

    assert provider.calls == 0
    assert bars.empty


def test_market_data_service_falls_back_when_primary_returns_empty():
    primary = EmptyProvider()
    fallback = FakeProvider()
    service = MarketDataService(provider=primary, data_root=_workspace_tmp())
    service.fallback_provider = fallback

    bars = service.get_bars("AAPL", period="5d", interval="15m", refresh=True)

    assert primary.calls == 1
    assert fallback.calls == 1
    assert len(bars) == 3
    assert bars.attrs["provider"] == "fake"
    metadata = service.load_metadata("AAPL", interval="15m", period="5d")
    assert metadata is not None
    assert metadata["provider"] == "fake"
    assert "FALLBACK_PROVIDER:fake" in metadata["issues"]


def test_refresh_returns_last_valid_cache_when_all_providers_fail():
    service = MarketDataService(provider=FakeProvider(), data_root=_workspace_tmp())
    original = service.get_bars("AAPL", period="1y", interval="1d")
    service.provider = ErrorProvider()
    service.fallback_provider = EmptyProvider()

    recovered = service.get_bars("AAPL", period="1y", interval="1d", refresh=True)

    assert recovered.equals(original)
    assert recovered.attrs["cache_fallback"] is True


def test_macro_history_propagates_refresh_to_source(monkeypatch):
    calls = []
    monkeypatch.setattr(
        macro_data.fred_client,
        "get_series",
        lambda symbol, **kwargs: calls.append((symbol, kwargs["refresh"])) or pd.DataFrame({"close": [4.0]}),
    )

    macro_data.get_macro_history("US10Y", refresh=True)

    assert calls == [("DGS10", True)]


def test_tiingo_primary_is_skipped_for_yahoo_native_futures_symbol():
    primary = EmptyProvider()
    primary.name = "tiingo"
    fallback = FakeProvider()
    service = MarketDataService(provider=primary, data_root=_workspace_tmp())
    service.fallback_provider = fallback

    bars = service.get_bars("NQ=F", period="1y", interval="1d", refresh=True)

    assert primary.calls == 0
    assert fallback.calls == 1
    assert bars.attrs["provider"] == "fake"
