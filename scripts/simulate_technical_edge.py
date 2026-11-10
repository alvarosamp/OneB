"""Walk-forward historical simulation of the Technical Edge Score.

Example:
    python -m scripts.simulate_technical_edge --period 2y --refresh

The script is intentionally a research simulation.  It selects the top 20%
of a fixed universe every five trading days, applies 14 bps to traded notional,
and does not model taxes, market impact, borrow, or intraday execution.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from app.market_data import service as market_data_service
from app.technical_edge import FEATURE_DIRECTIONS, feature_frame
from scripts.compare_recommendations import DEFAULT_SYMBOLS

HOLD_DAYS = 5
TOP_QUANTILE = 0.20
TURNOVER_COST_BPS = 14
OUT_PATH = Path("data/technical_edge_simulation.json")


def _max_drawdown(values: list[float]) -> float:
    peak = values[0] if values else 1.0
    drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        drawdown = min(drawdown, value / peak - 1)
    return drawdown * 100


def simulate(histories: dict[str, pd.DataFrame], benchmark: pd.DataFrame, start_pct: float = 0.0) -> dict:
    features = {symbol: feature_frame(history, benchmark) for symbol, history in histories.items()}
    common_dates = sorted(set.intersection(*(set(frame.index) for frame in features.values())))
    # 50 bars make every feature, including EMA50, meaningful.
    start = max(50, math.floor(len(common_dates) * start_pct))
    dates = common_dates[start::HOLD_DAYS]
    equity = 1.0
    curve = [equity]
    previous_weights: dict[str, float] = {}
    periods = []
    benchmark_equity = 1.0

    for date in dates:
        raw = []
        for symbol, frame in features.items():
            position = frame.index.get_loc(date)
            if isinstance(position, slice) or position + HOLD_DAYS >= len(frame):
                continue
            row = frame.iloc[position]
            if row[list(FEATURE_DIRECTIONS)].isna().any():
                continue
            raw.append({"symbol": symbol, **{name: float(row[name]) for name in FEATURE_DIRECTIONS}, "position": position})
        panel = pd.DataFrame(raw)
        if len(panel) < 10:
            continue

        contributions = []
        for feature, direction in FEATURE_DIRECTIONS.items():
            column = f"{feature}_rank"
            panel[column] = direction * (panel[feature].rank(pct=True) - 0.5)
            contributions.append(column)
        panel["score"] = panel[contributions].mean(axis=1)
        selected = panel.nlargest(max(1, math.floor(len(panel) * TOP_QUANTILE)), "score")
        weights = {symbol: 1 / len(selected) for symbol in selected["symbol"]}
        turnover = sum(abs(weights.get(symbol, 0) - previous_weights.get(symbol, 0)) for symbol in set(weights) | set(previous_weights))
        gross_return = 0.0
        for row in selected.itertuples(index=False):
            close = histories[row.symbol]["close"]
            gross_return += weights[row.symbol] * (float(close.iloc[row.position + HOLD_DAYS]) / float(close.iloc[row.position]) - 1)
        cost = turnover * TURNOVER_COST_BPS / 10_000
        net_return = gross_return - cost
        benchmark_position = benchmark.index.get_loc(date)
        benchmark_return = None
        if not isinstance(benchmark_position, slice) and benchmark_position + HOLD_DAYS < len(benchmark):
            benchmark_return = float(benchmark["close"].iloc[benchmark_position + HOLD_DAYS] / benchmark["close"].iloc[benchmark_position] - 1)
            benchmark_equity *= 1 + benchmark_return
        equity *= 1 + net_return
        curve.append(equity)
        periods.append({
            "date": str(pd.Timestamp(date).date()),
            "symbols": sorted(weights),
            "gross_return_pct": round(gross_return * 100, 4),
            "turnover": round(turnover, 4),
            "cost_pct": round(cost * 100, 4),
            "net_return_pct": round(net_return * 100, 4),
            "benchmark_return_pct": round(benchmark_return * 100, 4) if benchmark_return is not None else None,
            "equity": round(equity, 6),
        })
        previous_weights = weights

    returns = pd.Series([row["net_return_pct"] for row in periods], dtype=float)
    years = len(periods) * HOLD_DAYS / 252
    return {
        "config": {"hold_days": HOLD_DAYS, "top_quantile": TOP_QUANTILE, "turnover_cost_bps": TURNOVER_COST_BPS, "start_pct": start_pct, "features": FEATURE_DIRECTIONS},
        "summary": {
            "periods": len(periods),
            "total_return_pct": round((equity - 1) * 100, 4),
            "annualized_return_pct": round(((equity ** (1 / years)) - 1) * 100, 4) if years > 0 else None,
            "max_drawdown_pct": round(_max_drawdown(curve), 4),
            "hit_rate_pct": round(float((returns > 0).mean() * 100), 2) if not returns.empty else None,
            "average_period_return_pct": round(float(returns.mean()), 4) if not returns.empty else None,
            "average_turnover": round(float(pd.Series([row["turnover"] for row in periods]).mean()), 4) if periods else None,
            "benchmark_total_return_pct": round((benchmark_equity - 1) * 100, 4) if periods else None,
            "excess_return_pct": round((equity - benchmark_equity) * 100, 4) if periods else None,
        },
        "periods": periods,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default="2y")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--start-pct", type=float, default=0.0, help="Fraction of history to skip before simulation (0-0.95).")
    args = parser.parse_args()
    benchmark = market_data_service.get_bars("QQQ", period=args.period, interval="1d", refresh=args.refresh)
    histories = {symbol: market_data_service.get_bars(symbol, period=args.period, interval="1d", refresh=args.refresh) for symbol in DEFAULT_SYMBOLS}
    histories = {symbol: history for symbol, history in histories.items() if len(history) >= 100}
    if not 0 <= args.start_pct <= 0.95:
        raise SystemExit("--start-pct deve estar entre 0 e 0.95")
    report = simulate(histories, benchmark, start_pct=args.start_pct)
    report.update({"generated_at": datetime.now(timezone.utc).isoformat(), "period": args.period, "symbols": sorted(histories), "benchmark": "QQQ"})
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
