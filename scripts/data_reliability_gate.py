"""Data reliability gate for research/backtest inputs.

The goal is to fail loudly before a statistical audit uses suspicious data:
short fake caches, OHLC inconsistencies, large gaps, missing macro series or
unexpectedly stale histories. This is stricter than app runtime behavior,
because research should stop when the raw material is weak.

Run:
    python -m scripts.data_reliability_gate
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from app import paper_simulator as sim
from app.market_data import macro_data
from scripts.compare_recommendations import DEFAULT_SYMBOLS, _load_prepared, _symbols
from scripts.statistical_edge_audit import _normalize_index

OUT_PATH = Path("data/data_reliability_gate.json")
MIN_EQUITY_CANDLES = 240
MAX_SUSPICIOUS_GAPS = 0
MAX_CLOSE_STALENESS_DAYS = 10
MAX_BAD_OHLC_ROWS_PCT = 0.0
REQUIRED_MACRO = ["DXY", "US10Y", "VIX"]


def _bad_ohlc_pct(history: pd.DataFrame) -> float:
    if history.empty:
        return 100.0
    bad = (
        (history["high"] < history[["open", "close", "low"]].max(axis=1))
        | (history["low"] > history[["open", "close", "high"]].min(axis=1))
        | (history[["open", "high", "low", "close"]] <= 0).any(axis=1)
        | (history["volume"] < 0)
    )
    return float(bad.mean() * 100)


def _equity_rows(prepared: dict, skipped: list[str]) -> list[dict]:
    rows = []
    now = pd.Timestamp.now(tz=timezone.utc).tz_localize(None).normalize()
    for symbol, data in prepared.items():
        history = data["history"]
        dates = _normalize_index(history.index)
        gaps = pd.Series(dates).diff().dt.days.dropna()
        stale_days = int((now - dates.max()).days) if len(dates) else 9999
        bad_ohlc_pct = _bad_ohlc_pct(history)
        issues = []
        if len(history) < MIN_EQUITY_CANDLES:
            issues.append("SHORT_HISTORY")
        if int((gaps > 5).sum()) > MAX_SUSPICIOUS_GAPS:
            issues.append("SUSPICIOUS_GAPS")
        if stale_days > MAX_CLOSE_STALENESS_DAYS:
            issues.append("STALE_HISTORY")
        if bad_ohlc_pct > MAX_BAD_OHLC_ROWS_PCT:
            issues.append("BAD_OHLC")
        if history[["open", "high", "low", "close", "volume"]].isna().sum().sum() > 0:
            issues.append("MISSING_OHLCV")
        rows.append(
            {
                "symbol": symbol,
                "status": "PASS" if not issues else "FAIL",
                "issues": issues,
                "candles": int(len(history)),
                "start": str(dates.min().date()) if len(dates) else None,
                "end": str(dates.max().date()) if len(dates) else None,
                "stale_days": stale_days,
                "max_gap_days": int(gaps.max()) if not gaps.empty else 0,
                "suspicious_gaps_gt5d": int((gaps > 5).sum()),
                "bad_ohlc_pct": round(bad_ohlc_pct, 4),
            }
        )
    for symbol in skipped:
        rows.append({"symbol": symbol, "status": "FAIL", "issues": ["SKIPPED_BY_PREPARED_LOADER"]})
    return rows


def _macro_rows() -> list[dict]:
    rows = []
    for key in REQUIRED_MACRO:
        history = macro_data.get_macro_history(key, period=sim.MARKET_HISTORY_PERIOD, interval="1d")
        close = history["close"].dropna() if not history.empty and "close" in history else pd.Series(dtype=float)
        issues = []
        if close.empty:
            issues.append("EMPTY_MACRO")
        elif len(close) < MIN_EQUITY_CANDLES:
            issues.append("SHORT_MACRO_HISTORY")
        rows.append(
            {
                "key": key,
                "status": "PASS" if not issues else "FAIL",
                "issues": issues,
                "rows": int(len(close)),
                "start": str(close.index.min().date()) if not close.empty else None,
                "end": str(close.index.max().date()) if not close.empty else None,
                "last_value": None if close.empty else round(float(close.iloc[-1]), 6),
            }
        )
    return rows


def build_report() -> dict:
    symbols = _symbols() or DEFAULT_SYMBOLS
    prepared, _benchmark, skipped = _load_prepared(symbols)
    equities = _equity_rows(prepared, skipped)
    macro = _macro_rows()
    failures = [row for row in equities + macro if row["status"] != "PASS"]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbols_requested": symbols,
        "symbols_loaded": sorted(prepared),
        "status": "PASS" if not failures else "FAIL",
        "failure_count": len(failures),
        "equities": equities,
        "macro": macro,
        "failures": failures,
    }


def main() -> None:
    report = build_report()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("DATA RELIABILITY GATE")
    print("=" * 72)
    print(f"Status: {report['status']} | falhas: {report['failure_count']} | relatorio: {OUT_PATH}")
    if report["failures"]:
        print(pd.DataFrame(report["failures"]).to_string(index=False))
        raise SystemExit(1)
    print(f"Equities OK: {len(report['equities'])} | Macro OK: {len(report['macro'])}")


if __name__ == "__main__":
    main()
