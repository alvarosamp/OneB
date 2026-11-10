from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from app.market_data.providers import MarketDataProvider, MarketQuote, YahooMarketDataProvider, default_provider

DATA_ROOT = Path(os.getenv("MARKET_DATA_ROOT", "data"))
CACHE_ENABLED = os.getenv("MARKET_DATA_CACHE_ENABLED", "true").lower() == "true"
CACHE_ONLY = os.getenv("MARKET_DATA_CACHE_ONLY", "false").lower() == "true"
FORMAT_VERSION = 1
REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BarsMetadata:
    symbol: str
    provider: str
    period: str
    interval: str
    rows: int
    start: str | None
    end: str | None
    fetched_at: str
    source: str
    format_version: int = FORMAT_VERSION
    quality: str = "UNKNOWN"
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _safe_symbol(symbol: str) -> str:
    normalized = symbol.upper().strip()
    return re.sub(r"[^A-Z0-9._=-]+", "_", normalized)


def _cache_dir(provider_name: str, interval: str) -> Path:
    return DATA_ROOT / "raw" / "prices" / provider_name / interval


def _cache_paths(symbol: str, provider_name: str, interval: str) -> tuple[Path, Path]:
    base = _cache_dir(provider_name, interval) / _safe_symbol(symbol)
    return base.with_suffix(".csv"), base.with_suffix(".meta.json")


def _safe_period(period: str) -> str:
    return re.sub(r"[^A-Za-z0-9._=-]+", "_", period.strip().lower() or "default")


def normalize_bars(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    issues: list[str] = []
    if raw is None or raw.empty:
        return pd.DataFrame(columns=REQUIRED_COLUMNS), ["EMPTY_DATA"]

    df = raw.copy()
    df.columns = [str(column).lower() for column in df.columns]
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        return pd.DataFrame(columns=REQUIRED_COLUMNS), [f"MISSING_COLUMNS:{','.join(missing)}"]

    df = df[REQUIRED_COLUMNS]
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df[~df.index.isna()]
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]

    for column in REQUIRED_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    before = len(df)
    df = df.dropna(subset=["open", "high", "low", "close"])
    if len(df) < before:
        issues.append("DROPPED_INVALID_PRICE_ROWS")
    if "volume" in df.columns:
        df["volume"] = df["volume"].fillna(0)
    if df.empty:
        issues.append("EMPTY_AFTER_NORMALIZATION")
    return df, issues


class MarketDataService:
    def __init__(self, provider: MarketDataProvider | None = None, data_root: Path | None = None):
        self.provider = provider or default_provider
        self.fallback_provider = YahooMarketDataProvider()
        self.data_root = data_root or DATA_ROOT

    def _provider_chain(self, interval: str, symbol: str | None = None) -> list[MarketDataProvider]:
        normalized_symbol = (symbol or "").upper().strip()
        yahoo_native_symbol = normalized_symbol.endswith(("=F", "=X")) or normalized_symbol.startswith("^")
        if self.provider.name == "tiingo" and yahoo_native_symbol:
            return [self.fallback_provider]
        providers = [self.provider]
        if self.provider.name != self.fallback_provider.name:
            providers.append(self.fallback_provider)
        return providers

    def get_bars(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        *,
        use_cache: bool = CACHE_ENABLED,
        refresh: bool = False,
        cache_only: bool = CACHE_ONLY,
    ) -> pd.DataFrame:
        cached_fallback = self.load_cached_bars(symbol, period=period, interval=interval) if use_cache else None
        if use_cache and not refresh:
            if cached_fallback is not None and not cached_fallback.empty:
                return cached_fallback
        if cache_only:
            return pd.DataFrame(columns=REQUIRED_COLUMNS)

        for provider in self._provider_chain(interval, symbol):
            try:
                raw = provider.get_bars(symbol, period=period, interval=interval)
            except Exception:
                logger.exception("Falha isolada no provedor %s para %s", provider.name, symbol)
                continue
            bars, issues = normalize_bars(raw)
            if bars.empty:
                continue
            bars.attrs["provider"] = provider.name
            if provider.name != self.provider.name:
                issues = [*issues, f"FALLBACK_PROVIDER:{provider.name}"]
            if use_cache:
                self.save_bars(
                    symbol,
                    bars,
                    period=period,
                    interval=interval,
                    source="provider",
                    issues=issues,
                    provider_name=provider.name,
                )
            return bars
        if cached_fallback is not None and not cached_fallback.empty:
            cached_fallback.attrs["cache_fallback"] = True
            return cached_fallback
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    def refresh_bars(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        return self.get_bars(symbol, period=period, interval=interval, use_cache=True, refresh=True)

    def get_quote(self, symbol: str, *, use_cache: bool = CACHE_ENABLED, refresh: bool = False) -> MarketQuote | None:
        bars = self.get_bars(symbol, period="5d", interval="1d", use_cache=use_cache, refresh=refresh)
        if bars.empty:
            return None
        close = bars["close"].dropna()
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
            symbol=symbol.upper().strip(),
            price=latest,
            change_pct=change_pct,
            provider=bars.attrs.get("provider", self.provider.name),
            provider_time=provider_time,
            received_at=datetime.now(timezone.utc),
        )

    def load_cached_bars(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame | None:
        for provider in self._provider_chain(interval, symbol):
            for csv_path, meta_path in (
                self._paths(symbol, interval, period, provider.name),
                self._legacy_paths(symbol, interval, provider.name),
            ):
                if not csv_path.exists():
                    continue
                metadata = self._read_metadata(meta_path)
                if metadata and metadata.get("period") != period:
                    continue
                try:
                    df = pd.read_csv(csv_path)
                    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
                    df = df.set_index("timestamp")
                    bars, _ = normalize_bars(df)
                    bars.attrs["provider"] = provider.name
                    return bars
                except Exception:
                    continue
        return None

    def save_bars(
        self,
        symbol: str,
        bars: pd.DataFrame,
        *,
        period: str,
        interval: str,
        source: str,
        issues: list[str] | None = None,
        provider_name: str | None = None,
    ) -> BarsMetadata:
        provider = provider_name or self.provider.name
        csv_path, meta_path = self._paths(symbol, interval, period, provider)
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        out = bars.copy()
        out.index.name = "timestamp"
        out.to_csv(csv_path)

        metadata = BarsMetadata(
            symbol=symbol.upper().strip(),
            provider=provider,
            period=period,
            interval=interval,
            rows=len(bars),
            start=bars.index[0].isoformat() if len(bars) else None,
            end=bars.index[-1].isoformat() if len(bars) else None,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            source=source,
            quality="GOOD" if not issues else "WARN",
            issues=issues or [],
        )
        meta_path.write_text(json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return metadata

    def load_metadata(self, symbol: str, interval: str = "1d", period: str | None = None) -> dict | None:
        if period:
            for provider in self._provider_chain(interval, symbol):
                metadata = self._read_metadata(self._paths(symbol, interval, period, provider.name)[1])
                if metadata is not None:
                    return metadata
        for provider in self._provider_chain(interval, symbol):
            legacy = self._read_metadata(self._legacy_paths(symbol, interval, provider.name)[1])
            if legacy is not None:
                return legacy
            pattern = self.data_root / "raw" / "prices" / provider.name / interval
            for meta_path in sorted(pattern.glob(f"*/*{_safe_symbol(symbol)}.meta.json")):
                metadata = self._read_metadata(meta_path)
                if metadata is not None:
                    return metadata
        return None

    def _read_metadata(self, meta_path: Path) -> dict | None:
        if not meta_path.exists():
            return None
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _legacy_paths(self, symbol: str, interval: str, provider_name: str | None = None) -> tuple[Path, Path]:
        base = self.data_root / "raw" / "prices" / (provider_name or self.provider.name) / interval / _safe_symbol(symbol)
        return base.with_suffix(".csv"), base.with_suffix(".meta.json")

    def _paths(self, symbol: str, interval: str, period: str | None = None, provider_name: str | None = None) -> tuple[Path, Path]:
        if period:
            base = (
                self.data_root
                / "raw"
                / "prices"
                / (provider_name or self.provider.name)
                / interval
                / _safe_period(period)
                / _safe_symbol(symbol)
            )
            return base.with_suffix(".csv"), base.with_suffix(".meta.json")
        return self._legacy_paths(symbol, interval, provider_name)


default_service = MarketDataService()


def get_bars(
    symbol: str,
    period: str = "1y",
    interval: str = "1d",
    *,
    refresh: bool = False,
    cache_only: bool = CACHE_ONLY,
) -> pd.DataFrame:
    return default_service.get_bars(symbol, period=period, interval=interval, refresh=refresh, cache_only=cache_only)


def refresh_bars(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    return default_service.refresh_bars(symbol, period=period, interval=interval)


def get_quote(symbol: str, *, refresh: bool = False) -> MarketQuote | None:
    return default_service.get_quote(symbol, refresh=refresh)
