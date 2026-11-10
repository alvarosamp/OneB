"""Consolidate completed Tiingo monthly chunks without requesting more quota."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def consolidate(chunk_dir: Path, symbol: str, output: Path) -> dict:
    paths = sorted(chunk_dir.glob(f"{symbol.upper()}_5min_*_1.csv.gz"))
    if not paths:
        raise ValueError(f"No monthly chunks for {symbol} in {chunk_dir}")
    pieces = [pd.read_csv(path, parse_dates=["timestamp"]) for path in paths]
    raw = pd.concat(pieces, ignore_index=True)
    duplicates = int(raw["timestamp"].duplicated().sum())
    bars = raw.drop_duplicates("timestamp", keep="last").sort_values("timestamp").copy()
    invalid = (
        (bars["high"] < bars[["open", "close", "low"]].max(axis=1))
        | (bars["low"] > bars[["open", "close", "high"]].min(axis=1))
        | (bars[["open", "high", "low", "close"]] <= 0).any(axis=1)
    )
    invalid_count = int(invalid.sum())
    bars = bars.loc[~invalid].copy()
    if bars.empty:
        raise ValueError("All bars failed OHLC validation")
    observed_months = set(bars["timestamp"].dt.tz_convert("America/New_York").dt.tz_localize(None).dt.to_period("M"))
    calendar_months = pd.period_range(min(observed_months), max(observed_months), freq="M")
    missing_months = [str(month) for month in calendar_months if month not in observed_months]
    output.parent.mkdir(parents=True, exist_ok=True)
    bars.to_csv(output, index=False, compression="gzip")
    manifest = {
        "symbol": symbol.upper(),
        "instrument_type": "ETF_PROXY",
        "source": "Tiingo monthly 5min extended-hours chunks",
        "partial": True,
        "first": bars["timestamp"].min().isoformat(),
        "last": bars["timestamp"].max().isoformat(),
        "months_with_files": len(paths),
        "last_complete_chunk_end_exclusive": paths[-1].name.split("_")[3],
        "missing_calendar_months_within_observed_range": missing_months,
        "rows_raw": int(len(raw)),
        "duplicate_rows_removed": duplicates,
        "invalid_ohlc_rows_removed": invalid_count,
        "rows_final": int(len(bars)),
        "sessions": int(pd.Index(bars["timestamp"].dt.tz_convert("America/New_York").dt.date).nunique()),
        "output": str(output.resolve()),
        "sha256": sha256(output),
        "limitations": ["ETF is not NQ execution data", "Data collection stopped at provider quota; do not infer coverage after last timestamp"],
    }
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunk-dir", type=Path, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(consolidate(args.chunk_dir, args.symbol, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
