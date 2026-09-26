"""Download public Dukascopy M1 bid/ask data and create normalized gzip CSVs.

This source provides XAUUSD spot and USA 100 Technical Index CFDs, not CME GC
or NQ futures. The distinction is recorded in the generated manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

INSTRUMENTS = {
    "XAUUSD": {"dukascopy": "xauusd", "description": "Dukascopy spot gold"},
    "NAS100": {"dukascopy": "usatechidxusd", "description": "Dukascopy USA 100 Technical Index CFD"},
}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _csv_covers(path: Path, start: str, end: str) -> bool:
    if not path.exists() or path.stat().st_size <= 100:
        return False
    try:
        timestamps = pd.read_csv(path, usecols=["timestamp"])["timestamp"]
        observed_start = pd.to_datetime(timestamps.min(), unit="ms", utc=True).date()
        observed_end = pd.to_datetime(timestamps.max(), unit="ms", utc=True).date()
        return observed_start <= date.fromisoformat(start) + timedelta(days=7) and observed_end >= date.fromisoformat(end) - timedelta(days=7)
    except Exception:
        return False


def _download_range(
    instrument: str, price_type: str, timeframe: str, start: str, end: str, raw_dir: Path, stem: str
) -> Path:
    path = raw_dir / f"{stem}.csv"
    if _csv_covers(path, start, end):
        return path
    if path.exists():
        path.unlink()
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        raise RuntimeError("npx nao encontrado; instale Node.js/npm antes do download")
    command = [
        npx, "--yes", "dukascopy-node", "-i", INSTRUMENTS[instrument]["dukascopy"],
        "-from", start, "-to", end, "-t", timeframe, "-p", price_type,
        "-v", "-vu", "units", "-f", "csv", "-dir", str(raw_dir), "-fn", stem,
        "-bs", "1", "-bp", "3000", "-r", "8", "-rp", "5000", "-ch",
        "-chpath", str(raw_dir.parent / "cache"),
    ]
    last_error = None
    for attempt in range(5):
        try:
            subprocess.run(command, check=True)
            last_error = None
            break
        except subprocess.CalledProcessError as error:
            last_error = error
            time.sleep(min(30, 5 * 2**attempt))
    if last_error is not None:
        raise last_error
    if not path.exists() or path.stat().st_size <= 100:
        raise RuntimeError(f"Download nao produziu arquivo valido: {path}")
    return path


def download_side(
    instrument: str,
    price_type: str,
    timeframe: str,
    start: str,
    end: str,
    raw_dir: Path,
    chunk_days: int = 30,
) -> Path:
    label = timeframe.upper()
    destination = raw_dir / f"{instrument}_{price_type}_{label}_{start}_{end}.csv"
    if _csv_covers(destination, start, end):
        return destination
    chunk_dir = raw_dir / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    cursor = date.fromisoformat(start)
    final_date = date.fromisoformat(end)
    parts = []
    while cursor < final_date:
        chunk_end = min(final_date, cursor + timedelta(days=chunk_days))
        stem = f"{instrument}_{price_type}_{label}_{cursor.isoformat()}_{chunk_end.isoformat()}"
        parts.append(_download_range(instrument, price_type, timeframe, cursor.isoformat(), chunk_end.isoformat(), chunk_dir, stem))
        cursor = chunk_end
        time.sleep(2)
    frames = [pd.read_csv(part) for part in parts]
    combined = pd.concat(frames, ignore_index=True).drop_duplicates("timestamp").sort_values("timestamp")
    combined.to_csv(destination, index=False)
    return destination


def _read_side(path: Path, prefix: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    expected = {"timestamp", "open", "high", "low", "close", "volume"}
    if not expected <= set(frame.columns):
        raise ValueError(f"Esquema inesperado em {path}: {sorted(frame.columns)}")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    return frame.rename(columns={column: f"{prefix}_{column}" for column in ("open", "high", "low", "close", "volume")})


def normalize_pair(instrument: str, timeframe: str, bid_path: Path, ask_path: Path, output_dir: Path, start: str, end: str) -> tuple[Path, dict]:
    bid = _read_side(bid_path, "bid")
    ask = _read_side(ask_path, "ask")
    merged = bid.merge(ask, on="timestamp", how="inner", validate="one_to_one").sort_values("timestamp")
    for field in ("open", "high", "low", "close"):
        merged[field] = (merged[f"bid_{field}"] + merged[f"ask_{field}"]) / 2
    merged["volume"] = merged["bid_volume"].fillna(merged["ask_volume"]).fillna(0)
    merged["spread_open"] = merged["ask_open"] - merged["bid_open"]
    merged["spread_close"] = merged["ask_close"] - merged["bid_close"]
    columns = [
        "timestamp", "open", "high", "low", "close", "volume",
        "bid_open", "bid_high", "bid_low", "bid_close",
        "ask_open", "ask_high", "ask_low", "ask_close", "spread_open", "spread_close",
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{instrument}_{timeframe.upper()}_{start}_{end}.csv.gz"
    merged[columns].to_csv(destination, index=False, compression="gzip")
    positive_spread = merged["spread_open"].dropna()
    metadata = {
        "instrument": instrument,
        "description": INSTRUMENTS[instrument]["description"],
        "rows": int(len(merged)),
        "start": merged["timestamp"].min().isoformat() if len(merged) else None,
        "end": merged["timestamp"].max().isoformat() if len(merged) else None,
        "bid_rows": int(len(bid)),
        "ask_rows": int(len(ask)),
        "matched_ratio": round(float(len(merged) / max(len(bid), len(ask))), 6),
        "median_spread": round(float(positive_spread.median()), 6) if len(positive_spread) else None,
        "p95_spread": round(float(positive_spread.quantile(0.95)), 6) if len(positive_spread) else None,
        "output": str(destination.resolve()),
        "sha256": file_hash(destination),
    }
    return destination, metadata


def main() -> None:
    today = date.today()
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=Path(r"D:\OneB\market-data\dukascopy"))
    parser.add_argument("--start", default=(today - timedelta(days=365 * 3)).isoformat())
    parser.add_argument("--end", default=today.isoformat())
    parser.add_argument("--timeframe", choices=["m1", "m5"], default="m5")
    parser.add_argument("--instrument", action="append", choices=sorted(INSTRUMENTS), default=[])
    parser.add_argument(
        "--chunk-days",
        type=int,
        default=30,
        help="Days per downloader invocation. NAS100 is more reliable at 14 days than at 30.",
    )
    args = parser.parse_args()
    instruments = args.instrument or list(INSTRUMENTS)
    raw_dir = args.output_root / "raw"
    normalized_dir = args.output_root / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for instrument in instruments:
        if args.chunk_days < 1:
            raise ValueError("--chunk-days must be positive")
        bid = download_side(instrument, "bid", args.timeframe, args.start, args.end, raw_dir, args.chunk_days)
        ask = download_side(instrument, "ask", args.timeframe, args.start, args.end, raw_dir, args.chunk_days)
        _, metadata = normalize_pair(instrument, args.timeframe, bid, ask, normalized_dir, args.start, args.end)
        metadata["raw_bid_sha256"] = file_hash(bid)
        metadata["raw_ask_sha256"] = file_hash(ask)
        records.append(metadata)
    manifest = {
        "source": "Dukascopy public historical feed via dukascopy-node",
        "source_pages": {
            "XAUUSD": "https://www.dukascopy-node.app/instrument/xauusd",
            "NAS100": "https://www.dukascopy-node.app/instrument/usatechidxusd",
        },
        "warning": "XAUUSD spot and NAS100 CFD are not CME GC/NQ futures; results cannot be relabeled as futures evidence.",
        "timeframe": args.timeframe.upper(),
        "date_from": args.start,
        "date_to_exclusive": args.end,
        "chunk_days": args.chunk_days,
        "datasets": records,
    }
    manifest_path = args.output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
