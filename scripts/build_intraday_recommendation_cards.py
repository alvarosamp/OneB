"""Create auditable Nasdaq/gold decision cards from frozen broker data.

The gate intentionally emits NO_TRADE until a setup has enough broker sessions
and independent evidence. It never derives a win probability from a score.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


DEFAULT_BROKER = Path(r"D:\OneB\market-data\mt5\HonorPro\synced-2026-09-25")
DEFAULT_RESEARCH = Path("output/vendor_indicator_research/prescribed_timeframes_v1/results.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_bars(path: Path, as_of: pd.Timestamp) -> tuple[pd.DataFrame, pd.Timestamp]:
    frame = pd.read_csv(path, parse_dates=["timestamp"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.drop_duplicates("timestamp", keep="last").sort_values("timestamp")
    source_latest = frame["timestamp"].max()
    # Broker M5 timestamps are bar opens. Only a fully closed bar is known.
    frame = frame.loc[frame["timestamp"] + pd.Timedelta(minutes=5) <= as_of].copy()
    if frame.empty:
        raise ValueError(f"No completed bars at {as_of} in {path}")
    bad = (
        (frame["high"] < frame[["open", "close", "low"]].max(axis=1))
        | (frame["low"] > frame[["open", "close", "high"]].min(axis=1))
        | (frame[["open", "high", "low", "close"]] <= 0).any(axis=1)
    )
    if bad.any():
        raise ValueError(f"Invalid OHLC rows in {path}: {int(bad.sum())}")
    return frame.set_index("timestamp"), source_latest


def _research_row(path: Path, family: str) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return next((row for row in payload["results"] if row["family"] == family), {})


def build_card(symbol: str, path: Path, research: dict, as_of: pd.Timestamp) -> dict:
    frame, source_latest = _load_bars(path, as_of)
    latest = frame.iloc[-1]
    last_time = frame.index[-1]
    sessions = int(pd.Index(frame.index.tz_convert("America/New_York").date).nunique())
    point = 0.1 if symbol == "US100.s" else 0.01
    spread = frame["spread"].astype(float) * point
    timestamp_ahead_minutes = max(0.0, (source_latest - as_of).total_seconds() / 60)
    clock_ok = timestamp_ahead_minutes <= 5
    fresh = clock_ok and as_of - (last_time + pd.Timedelta(minutes=5)) <= pd.Timedelta(minutes=20)
    holdout = research.get("holdout", {})
    reasons = []
    if not clock_ok:
        reasons.append(f"Timestamp MT5 {timestamp_ahead_minutes:.0f} min a frente do UTC local; fuso do servidor nao reconciliado.")
    if not fresh:
        reasons.append("Cotacao intradiaria desatualizada.")
    if sessions < 250:
        reasons.append(f"Historico da corretora: {sessions} sessoes; minimo de pesquisa: 250.")
    if not research or research.get("classification") != "approved_for_paper_trading":
        reasons.append("Setup sem aprovacao fora da amostra apos custos e multiplos testes.")
    if holdout.get("bh_q_value") is not None and holdout["bh_q_value"] > 0.10:
        reasons.append(f"q-value do holdout {holdout['bh_q_value']:.3f} acima do limite 0,10.")
    return {
        "symbol": symbol,
        "instrument_type": "BROKER_CFD",
        "source": "HonorPro MT5",
        "timeframe": "M5",
        "as_of": last_time.isoformat(),
        "market_price": round(float(latest["close"]), 2 if point == 0.01 else 1),
        "action": "NO_TRADE" if reasons else "WATCH",
        "direction": None,
        "entry_price": None,
        "stop_price": None,
        "take_profit": [],
        "risk_reward": None,
        "confidence_pct": None,
        "setup_family": research.get("family"),
        "data_health": {
            "sessions": sessions,
            "rows": int(len(frame)),
            "fresh": bool(fresh),
            "source_latest_timestamp": source_latest.isoformat(),
            "timestamp_ahead_minutes": round(timestamp_ahead_minutes, 1),
            "median_spread_price": round(float(spread.median()), 4),
            "p95_spread_price": round(float(spread.quantile(0.95)), 4),
        },
        "holdout_evidence": {
            "trades": holdout.get("trades"),
            "profit_factor": holdout.get("profit_factor"),
            "expectancy": holdout.get("expectancy"),
            "bh_q_value": holdout.get("bh_q_value"),
        },
        "reasons": reasons,
        "input_sha256": _sha256(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--broker-dir", type=Path, default=DEFAULT_BROKER)
    parser.add_argument("--research", type=Path, default=DEFAULT_RESEARCH)
    parser.add_argument("--output", type=Path, default=Path("data/research/intraday_cards/latest.json"))
    parser.add_argument("--as-of", help="UTC timestamp for reproducible historical snapshots")
    args = parser.parse_args()
    as_of = pd.Timestamp(args.as_of) if args.as_of else pd.Timestamp.now(tz="UTC")
    if as_of.tzinfo is None:
        as_of = as_of.tz_localize("UTC")
    as_of = as_of.tz_convert("UTC")
    paths = {
        "US100.s": next(args.broker_dir.glob("US100.s_M5_*.csv.gz")),
        "XAUUSD.s": next(args.broker_dir.glob("XAUUSD.s_M5_*.csv.gz")),
    }
    cards = [
        build_card("US100.s", paths["US100.s"], _research_row(args.research, "nasdaq_gap_drive_proxy"), as_of),
        build_card("XAUUSD.s", paths["XAUUSD.s"], _research_row(args.research, "london_box"), as_of),
    ]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision_as_of": as_of.isoformat(),
        "status": "RESEARCH_ONLY",
        "method": "Completed M5 broker bars; minimum 250 broker sessions; holdout q<=0.10; no calibrated probability available.",
        "cards": cards,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
