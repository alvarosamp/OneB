"""Evaluate frozen vendor-strategy parameters on neighbouring timeframes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from intraday_setup_research import load_intraday_csv, resample_bars
from vendor_strategy_backtest import COSTS, features, grids, metrics, simulate

PRESCRIBED = {
    "gold_fakeout": 10,
    "13x": None,
    "100_pips": None,
    "duck": 5,
    "london_box": 60,
    "nasdaq_gap_drive_proxy": 1,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nq-m1", type=Path, required=True)
    ap.add_argument("--xau-m5", type=Path, required=True)
    ap.add_argument("--selected", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    selected_rows = json.loads(args.selected.read_text(encoding="utf-8"))
    selected = {row["family"]: row["parameters"] for row in selected_rows}
    # Gap Drive did not complete in v1; use a declared, frozen OHLC baseline.
    selected["nasdaq_gap_drive_proxy"] = {"stop_atr": 1.0, "reward_r": 1.5, "hold_minutes": 120, "hour_ny": 18, "direction": "first_bar"}
    base = {
        "NQ": load_intraday_csv(args.nq_m1, "America/New_York"),
        "XAUUSD": load_intraday_csv(args.xau_m5, "UTC"),
    }
    functions = {family: (symbol, fn) for family, (symbol, fn, _) in grids().items()}
    rows = []
    for symbol, periods in {"NQ": (1, 5, 10, 15, 30, 60), "XAUUSD": (5, 10, 15, 30, 60)}.items():
        native = 1 if symbol == "NQ" else 5
        for minutes in periods:
            bars = base[symbol] if minutes == native else resample_bars(base[symbol], minutes)
            f = features(bars)
            dates = sorted(pd.unique(f.date))
            holdout = set(dates[int(.8 * len(dates)):])
            for family, (required_symbol, fn) in functions.items():
                portable = family in {"13x", "100_pips", "duck"}
                if required_symbol != symbol and not portable:
                    continue
                p = selected[family]
                signal = fn(f, p)
                result = metrics(simulate(f, signal, COSTS[symbol], p, holdout))
                rows.append({"family": family, "symbol": symbol, "timeframe_minutes": minutes,
                             "prescribed_timeframe": PRESCRIBED[family], "is_prescribed": PRESCRIBED[family] in (None, minutes),
                             **result})
            print(f"DONE {symbol} M{minutes}", flush=True)
    table = pd.DataFrame(rows)
    table.to_csv(args.output / "timeframe_sensitivity.csv", index=False)
    (args.output / "timeframe_sensitivity.json").write_text(table.to_json(orient="records", indent=2), encoding="utf-8")
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
