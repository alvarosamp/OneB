"""Export consolidated intraday ETF bars from Tiingo for proxy research.

QQQ and SPY are deliberately labelled as proxies.  They must not be joined to
NQ/ES futures as though prices, trading hours, volume, or execution costs were
identical.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import httpx
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings


BASE_URL = "https://api.tiingo.com/tiingo/equity/intraday"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fetch_chunk(symbol: str, start: str, end: str, frequency: str, extended_hours: bool) -> pd.DataFrame:
    if not settings.tiingo_api_key:
        raise RuntimeError("TIINGO_API_KEY is not configured")
    response = httpx.get(
        f"{BASE_URL}/{symbol.lower()}/prices",
        params={
            "startDate": start,
            "endDate": end,
            "resampleFreq": frequency,
            "columns": "open,high,low,close,volume",
            "afterHours": str(extended_hours).lower(),
        },
        headers={"Authorization": f"Token {settings.tiingo_api_key}"},
        timeout=120.0,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or not payload:
        raise RuntimeError(f"No intraday data returned for {symbol}")
    bars = pd.DataFrame(payload)
    required = {"date", "open", "high", "low", "close"}
    if not required.issubset(bars.columns):
        raise RuntimeError(f"Unexpected Tiingo fields for {symbol}: {sorted(bars.columns)}")
    bars = bars.rename(columns={"date": "timestamp"})
    bars["timestamp"] = pd.to_datetime(bars["timestamp"], utc=True, errors="raise")
    if "volume" not in bars:
        bars["volume"] = 0
    for column in ("open", "high", "low", "close", "volume"):
        bars[column] = pd.to_numeric(bars[column], errors="coerce")
    return bars[["timestamp", "open", "high", "low", "close", "volume"]].dropna(
        subset=["timestamp", "open", "high", "low", "close"]
    ).drop_duplicates("timestamp", keep="last").sort_values("timestamp")


def fetch(symbol: str, start: str, end: str, frequency: str, extended_hours: bool, chunk_dir: Path | None = None) -> pd.DataFrame:
    """Fetch in calendar-month chunks to avoid Tiingo's per-response row cap."""
    first = pd.Timestamp(start)
    last = pd.Timestamp(end)
    # RTH has ~78 five-minute bars/session, so four-month chunks remain well
    # below 10k. Extended hours has ~192 and therefore uses monthly chunks.
    frequency_rule = "MS" if extended_hours else "4MS"
    boundaries = list(pd.date_range(first.normalize(), last.normalize(), freq=frequency_rule))
    if not boundaries or boundaries[0] > first:
        boundaries.insert(0, first)
    if boundaries[-1] < last:
        boundaries.append(last)
    elif boundaries[-1] > last:
        boundaries[-1] = last
    parts: list[pd.DataFrame] = []
    for chunk_start, chunk_end in zip(boundaries, boundaries[1:]):
        chunk_path = None
        if chunk_dir is not None:
            chunk_dir.mkdir(parents=True, exist_ok=True)
            chunk_path = chunk_dir / f"{symbol.upper()}_{frequency}_{chunk_start.date()}_{chunk_end.date()}_{int(extended_hours)}.csv.gz"
        if chunk_path is not None and chunk_path.exists():
            part = pd.read_csv(chunk_path, parse_dates=["timestamp"])
            if part.empty or len(part) >= 10_000:
                raise RuntimeError(f"Invalid cached Tiingo chunk: {chunk_path}")
            parts.append(part)
            continue
        for attempt in range(4):
            try:
                part = _fetch_chunk(
                    symbol, chunk_start.date().isoformat(), chunk_end.date().isoformat(), frequency, extended_hours
                )
                break
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 429 or attempt == 3:
                    raise
                retry_after = int(exc.response.headers.get("Retry-After", "15"))
                time.sleep(min(max(retry_after, 5), 60))
        if len(part) >= 10_000:
            raise RuntimeError(
                f"Tiingo response cap reached for {symbol} {chunk_start.date()}..{chunk_end.date()}; "
                "reduce the chunk size"
            )
        if chunk_path is not None:
            part.to_csv(chunk_path, index=False, compression="gzip")
        parts.append(part)
    if not parts:
        raise RuntimeError(f"No intraday data returned for {symbol}")
    return pd.concat(parts, ignore_index=True).drop_duplicates("timestamp", keep="last").sort_values("timestamp")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", action="append", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--frequency", default="5min", choices=("1min", "5min", "15min", "30min", "1hour"))
    parser.add_argument("--extended-hours", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("data/intraday/tiingo"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for symbol in args.symbol:
        bars = fetch(symbol, args.start, args.end, args.frequency, args.extended_hours, args.output / "chunks")
        invalid = (
            (bars["high"] < bars[["open", "close", "low"]].max(axis=1))
            | (bars["low"] > bars[["open", "close", "high"]].min(axis=1))
            | (bars[["open", "high", "low", "close"]] <= 0).any(axis=1)
        )
        invalid_count = int(invalid.sum())
        bars = bars.loc[~invalid].copy()
        if bars.empty:
            raise RuntimeError(f"No valid OHLC rows for {symbol}")
        path = args.output / f"{symbol.upper()}_{args.frequency}_{args.start}_{args.end}.csv.gz"
        bars.to_csv(path, index=False, compression="gzip")
        manifest = {
            "symbol": symbol.upper(),
            "instrument_type": "ETF_PROXY",
            "proxy_for": "NASDAQ_100" if symbol.upper() == "QQQ" else "SP500" if symbol.upper() == "SPY" else None,
            "source": "Tiingo consolidated equity intraday",
            "frequency": args.frequency,
            "includes_extended_hours": args.extended_hours,
            "start_returned": bars.timestamp.min().isoformat(),
            "end_returned": bars.timestamp.max().isoformat(),
            "rows": int(len(bars)),
            "invalid_ohlc_rows_excluded": invalid_count,
            "output": str(path.resolve()),
            "sha256": sha256(path),
            "limitations": [
                "ETF proxy is not a futures or CFD execution series",
                "ETF trading hours, dividends, volume and costs differ from NQ/ES and broker CFDs",
            ],
        }
        path.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
