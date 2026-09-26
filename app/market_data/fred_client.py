"""Official macro series via the FRED (Federal Reserve Economic Data) API.

Used for Treasury yields and the trade-weighted dollar index instead of the
Yahoo proxies previously in yfinance_client.MACRO_INSTRUMENTS — FRED is the
primary source these series come from (St. Louis Fed), not a redistributor,
and it's also where the missing 2-Year Treasury yield (DGS2) comes from.

Requires settings.fred_api_key (free, no credit card:
https://fred.stlouisfed.org/docs/api/api_key.html). Every function here
degrades to None/empty on missing key or request failure, same fail-open
pattern as the LLM providers in app/config.py.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
import pandas as pd

from app.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
RELEASE_DATES_URL = "https://api.stlouisfed.org/fred/releases/dates"
PROVIDER_NAME = "fred"
PROVIDER_ROLE = "official_macro_series"
DATA_ROOT = Path(os.getenv("MARKET_DATA_ROOT", "data"))
CACHE_ENABLED = os.getenv("FRED_CACHE_ENABLED", "true").lower() == "true"

_COLUMNS = ["open", "high", "low", "close", "volume"]


def _cache_path(series_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "._=-" else "_" for ch in series_id.upper())
    return DATA_ROOT / "raw" / "macro" / PROVIDER_NAME / f"{safe}.csv"


def _load_cached_series(series_id: str) -> pd.DataFrame:
    path = _cache_path(series_id)
    if not path.exists():
        return pd.DataFrame(columns=_COLUMNS)
    try:
        df = pd.read_csv(path, parse_dates=["timestamp"]).set_index("timestamp")
    except Exception:
        logger.warning("Cache FRED invalido para %s em %s.", series_id, path, exc_info=True)
        return pd.DataFrame(columns=_COLUMNS)
    missing = [column for column in _COLUMNS if column not in df.columns]
    if missing:
        return pd.DataFrame(columns=_COLUMNS)
    return df[_COLUMNS].sort_index()


def _save_cached_series(series_id: str, history: pd.DataFrame) -> None:
    if history.empty:
        return
    path = _cache_path(series_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = history.copy()
    out.index.name = "timestamp"
    out.to_csv(path)

# Curated high-impact macro releases — FRED's /releases/dates endpoint returns
# hundreds of low-relevance releases per day (e.g. "Coinbase Cryptocurrencies")
# if unfiltered; this whitelist is what actually moves markets. IDs confirmed
# against GET /fred/releases during this session's data audit.
HIGH_IMPACT_RELEASES: dict[int, str] = {
    101: "FOMC Press Release",
    50: "Employment Situation (NFP)",
    10: "Consumer Price Index (CPI)",
    53: "Gross Domestic Product (GDP)",
    54: "Personal Income and Outlays (PCE)",
    9: "Advance Monthly Retail Sales",
}


@dataclass
class EconomicEventEntry:
    event_name: str
    country: str
    event_date: datetime
    impact: str
    actual: str
    forecast: str
    previous: str


@dataclass
class FredQuote:
    series_id: str
    name: str
    value: float
    change_pct: float
    updated_at: datetime


def get_series(
    series_id: str,
    observation_start: str | None = None,
    *,
    use_cache: bool = CACHE_ENABLED,
    refresh: bool = False,
) -> pd.DataFrame:
    """Daily observation history for a FRED series (e.g. "DGS10").

    Returns a DataFrame shaped like yfinance_client.get_history (columns
    open/high/low/close/volume, indexed by timestamp) so it's a drop-in
    replacement for callers that only care about `close`. FRED series are a
    single daily value, not OHLC, so all four price columns hold that value
    and volume is 0.
    """
    if use_cache and not refresh:
        cached = _load_cached_series(series_id)
        if not cached.empty:
            return cached

    if not settings.fred_api_key:
        logger.warning("FRED_API_KEY nao configurada — series %s indisponivel.", series_id)
        return _load_cached_series(series_id) if use_cache else pd.DataFrame(columns=_COLUMNS)

    params = {
        "series_id": series_id,
        "api_key": settings.fred_api_key,
        "file_type": "json",
    }
    if observation_start:
        params["observation_start"] = observation_start

    try:
        response = httpx.get(BASE_URL, params=params, timeout=10.0)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        logger.exception("Falha ao buscar serie %s no FRED", series_id)
        return _load_cached_series(series_id) if use_cache else pd.DataFrame(columns=_COLUMNS)

    observations = payload.get("observations", [])
    if not observations:
        return pd.DataFrame(columns=_COLUMNS)

    rows = []
    index = []
    for obs in observations:
        # FRED marks missing days (holidays, not-yet-published) with "."
        if obs["value"] == ".":
            continue
        value = float(obs["value"])
        rows.append({"open": value, "high": value, "low": value, "close": value, "volume": 0.0})
        index.append(pd.Timestamp(obs["date"]))

    if not rows:
        return pd.DataFrame(columns=_COLUMNS)

    out = pd.DataFrame(rows, index=pd.DatetimeIndex(index, name="timestamp"))
    if use_cache:
        _save_cached_series(series_id, out[_COLUMNS])
    return out[_COLUMNS]


def get_quote(series_id: str, name: str, *, refresh: bool = False) -> FredQuote | None:
    """Latest value plus day-over-day change for a FRED series."""
    history = get_series(series_id, refresh=refresh)
    if history.empty:
        return None

    close = history["close"].dropna()
    if close.empty:
        return None

    latest = float(close.iloc[-1])
    previous = float(close.iloc[-2]) if len(close) >= 2 else latest
    change_pct = ((latest - previous) / previous * 100) if previous else 0.0

    timestamp = close.index[-1]
    updated_at = timestamp.to_pydatetime() if hasattr(timestamp, "to_pydatetime") else datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    return FredQuote(series_id=series_id, name=name, value=latest, change_pct=change_pct, updated_at=updated_at)


def get_economic_calendar(from_date: date, to_date: date) -> list[EconomicEventEntry]:
    """High-impact US macro release dates in [from_date, to_date], sourced
    from FRED's official release calendar and filtered to
    HIGH_IMPACT_RELEASES. Replaces app.market_data.fmp_client's version,
    whose underlying FMP endpoint was retired (see fmp_client module
    docstring) — this one needs no separate signup, just settings.fred_api_key.

    FRED's release-dates endpoint gives only the date a release happens,
    not the actual/forecast/previous values (those live on the release's
    individual series and would need a separate per-series fetch) — those
    three fields are left blank here rather than guessed.
    """
    if not settings.fred_api_key:
        logger.warning("FRED_API_KEY nao configurada — calendario economico indisponivel.")
        return []

    try:
        response = httpx.get(
            RELEASE_DATES_URL,
            params={
                "api_key": settings.fred_api_key,
                "file_type": "json",
                "realtime_start": from_date.isoformat(),
                "realtime_end": to_date.isoformat(),
                "include_release_dates_with_no_data": "false",
            },
            timeout=15.0,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        logger.exception("Falha ao buscar calendario economico no FRED")
        return []

    entries = []
    for item in payload.get("release_dates", []):
        release_id = item.get("release_id")
        if release_id not in HIGH_IMPACT_RELEASES:
            continue
        try:
            event_date = datetime.fromisoformat(item["date"]).replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        entries.append(
            EconomicEventEntry(
                event_name=HIGH_IMPACT_RELEASES[release_id],
                country="US",
                event_date=event_date,
                impact="high",
                actual="",
                forecast="",
                previous="",
            )
        )
    return entries
