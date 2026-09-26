"""Normalize and audit third-party NQ/XAUUSD intraday CSVs.

The output is deliberately boring: one timezone-aware timestamp column plus
OHLCV, sorted and de-duplicated.  No missing candles are forward-filled.  A
JSON audit records coverage, gaps and basic OHLC integrity before the files are
allowed into the strategy research pipeline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path, source_timezone: str) -> pd.DataFrame:
    frame = pd.read_csv(path, sep=None, engine="python")
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    timestamp_column = next(
        (column for column in frame.columns if column in {"timestamp", "datetime", "date"} or column.startswith("timestamp ")),
        None,
    )
    if timestamp_column is None:
        raise ValueError(f"No timestamp column in {path}")
    required = ["open", "high", "low", "close"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing OHLC columns in {path}: {missing}")
    keep = [timestamp_column, *required] + (["volume"] if "volume" in frame.columns else [])
    frame = frame[keep].rename(columns={timestamp_column: "timestamp"})
    if "volume" not in frame:
        frame["volume"] = 0.0
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="raise")
    for column in [*required, "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["timestamp", *required])
    index = pd.DatetimeIndex(frame.pop("timestamp"))
    if index.tz is None:
        index = index.tz_localize(source_timezone, ambiguous="NaT", nonexistent="shift_forward")
    frame.index = index
    frame = frame[~frame.index.isna()].sort_index()
    return frame[~frame.index.duplicated(keep="last")]


def _resample(frame: pd.DataFrame, minutes: int) -> pd.DataFrame:
    return frame.resample(f"{minutes}min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna(subset=["open", "high", "low", "close"])


def _audit(frame: pd.DataFrame, expected_minutes: int) -> dict[str, object]:
    delta = frame.index.to_series().diff().dt.total_seconds().div(60)
    bad_ohlc = (
        (frame["high"] < frame[["open", "close"]].max(axis=1))
        | (frame["low"] > frame[["open", "close"]].min(axis=1))
        | (frame["high"] < frame["low"])
    )
    returns = frame["close"].pct_change().replace([np.inf, -np.inf], np.nan)
    sessions = pd.Index(frame.index.tz_convert("America/New_York").date).nunique()
    return {
        "rows": int(len(frame)),
        "start": frame.index.min().isoformat(),
        "end": frame.index.max().isoformat(),
        "sessions": int(sessions),
        "duplicate_timestamps": int(frame.index.duplicated().sum()),
        "invalid_ohlc_rows": int(bad_ohlc.sum()),
        "negative_volume_rows": int((frame["volume"] < 0).sum()),
        "median_bar_minutes": float(delta.median()),
        "gaps_over_3_bars": int((delta > expected_minutes * 3).sum()),
        "zero_volume_fraction": float((frame["volume"] == 0).mean()),
        "return_abs_p999": float(returns.abs().quantile(0.999)),
        "return_abs_max": float(returns.abs().max()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--source-timezone", required=True)
    parser.add_argument("--input-minutes", type=int, required=True)
    parser.add_argument("--output-minutes", type=int, default=5)
    parser.add_argument("--start", default=None, help="Inclusive ISO date")
    parser.add_argument("--end", default=None, help="Exclusive ISO date")
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()

    frame = _load(args.input, args.source_timezone)
    if args.start:
        frame = frame[frame.index >= pd.Timestamp(args.start, tz=args.source_timezone)]
    if args.end:
        frame = frame[frame.index < pd.Timestamp(args.end, tz=args.source_timezone)]
    if args.output_minutes < args.input_minutes or args.output_minutes % args.input_minutes:
        raise ValueError("output-minutes must be an integer multiple of input-minutes")
    if args.output_minutes != args.input_minutes:
        frame = _resample(frame, args.output_minutes)
    if frame.empty:
        raise ValueError("No rows remain after filtering")

    # Persist one unambiguous timezone.  Local wall-clock offsets change at DST
    # boundaries and would otherwise create mixed-offset CSV strings.
    frame.index = frame.index.tz_convert("UTC")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    output = frame.reset_index(names="timestamp")
    output.to_csv(args.output, index=False, compression="infer")
    audit = {
        "symbol": args.symbol.upper(),
        "source": str(args.input.resolve()),
        "source_sha256": _sha256(args.input),
        "output": str(args.output.resolve()),
        "output_sha256": _sha256(args.output),
        "source_timezone": args.source_timezone,
        "output_minutes": args.output_minutes,
        **_audit(frame, args.output_minutes),
    }
    args.audit.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
