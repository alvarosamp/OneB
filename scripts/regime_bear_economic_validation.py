"""Economic, out-of-sample validation for the BEAR-regime research signal."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.compare_recommendations import DEFAULT_SYMBOLS, _load_prepared, _symbols
from scripts.cross_sectional_ic import _build_panel
from scripts.data_reliability_gate import build_report as build_data_gate
from scripts.regime_signal_evidence import _add_label_and_regime, _fit_scores
from scripts.research_folds import date_based_folds

HORIZON_DAYS, TOP_QUANTILE, ROUND_TRIP_COST_BPS, MIN_SYMBOLS_PER_DATE, MIN_ECONOMIC_PERIODS = 5, 0.20, 20.0, 10, 24


def max_drawdown(equity: list[float]) -> float:
    peak, worst = 1.0, 0.0
    for value in equity:
        peak, worst = max(peak, value), min(worst, value / peak - 1)
    return worst


def turnover(previous: dict[str, float], current: dict[str, float]) -> float:
    return sum(abs(current.get(symbol, 0.0) - previous.get(symbol, 0.0)) for symbol in set(previous) | set(current))


def simulate_top_quantile(holdout: pd.DataFrame, *, score_column: str = "volatility_atr", top_quantile: float = TOP_QUANTILE, round_trip_cost_bps: float = ROUND_TRIP_COST_BPS, horizon_days: int = HORIZON_DAYS) -> dict:
    """Simulate a long-only portfolio from already-held-out cross-sectional rows."""
    required = {"date", "symbol", score_column, "fwd_return_5d"}
    if holdout.empty or not required.issubset(holdout.columns):
        return {"periods": [], "summary": {"periods": 0, "net_return_pct": None}}
    dates = sorted(pd.to_datetime(holdout["date"]).drop_duplicates())
    equity, previous, periods = [1.0], {}, []
    for date in dates[::horizon_days]:
        group = holdout[pd.to_datetime(holdout["date"]) == date].dropna(subset=[score_column, "fwd_return_5d"])
        if len(group) < MIN_SYMBOLS_PER_DATE:
            continue
        picks = group.nlargest(max(1, int(len(group) * top_quantile)), score_column)
        weights = {str(row.symbol): 1 / len(picks) for row in picks.itertuples(index=False)}
        gross = sum(weights[str(row.symbol)] * float(row.fwd_return_5d) / 100 for row in picks.itertuples(index=False))
        equal_weight, turn = float(group["fwd_return_5d"].mean()) / 100, turnover(previous, weights)
        cost, net = turn * round_trip_cost_bps / 10000, gross - turn * round_trip_cost_bps / 10000
        equity.append(equity[-1] * (1 + net))
        periods.append({"date": str(pd.Timestamp(date).date()), "positions": sorted(weights), "gross_return_pct": round(gross * 100, 4), "net_return_pct": round(net * 100, 4), "equal_weight_return_pct": round(equal_weight * 100, 4), "turnover": round(turn, 4), "cost_bps": round(cost * 10000, 4), "equity": round(equity[-1], 6)})
        previous = weights
    returns = pd.Series([row["net_return_pct"] / 100 for row in periods], dtype=float)
    equal_returns = pd.Series([row["equal_weight_return_pct"] / 100 for row in periods], dtype=float)
    total = equity[-1] - 1
    annual_factor = 252 / horizon_days / len(periods) if periods else 0
    enough_periods = len(periods) >= MIN_ECONOMIC_PERIODS
    return {"periods": periods, "summary": {"periods": len(periods), "minimum_required_periods": MIN_ECONOMIC_PERIODS, "sample_adequate": enough_periods, "net_return_pct": round(total * 100, 4) if periods else None, "annualized_return_approx_pct": round(((1 + total) ** annual_factor - 1) * 100, 4) if enough_periods else None, "max_drawdown_pct": round(max_drawdown(equity) * 100, 4) if periods else None, "hit_rate": round(float((returns > 0).mean()), 4) if len(returns) else None, "avg_turnover": round(float(pd.Series([row["turnover"] for row in periods]).mean()), 4) if periods else None, "equal_weight_return_pct": round(((1 + equal_returns).prod() - 1) * 100, 4) if len(equal_returns) else None}}


def build_report(symbols: list[str] | None = None, cost_bps: float = ROUND_TRIP_COST_BPS) -> dict:
    gate = build_data_gate()
    if gate["status"] != "PASS":
        return {"status": "BLOCKED_BY_DATA_GATE", "data_gate": gate}
    prepared, benchmark, skipped = _load_prepared(symbols or _symbols() or DEFAULT_SYMBOLS)
    bear = _add_label_and_regime(_build_panel(prepared, benchmark))
    bear = bear[bear["regime"] == "BEAR"].replace([float("inf"), float("-inf")], pd.NA).dropna(subset=["annualized_volatility", "atr_pct"])
    folds = date_based_folds(bear["date"], num_folds=4, window_days=bear["date"].nunique(), embargo_days=10)
    if len(folds) < 2:
        return {"status": "INSUFFICIENT_BEAR_DATES", "data_gate": gate}
    *train_folds, holdout_fold = folds
    rows_for = lambda interval: bear[(bear["date"] >= interval[0]) & (bear["date"] < interval[1])]
    train, holdout = pd.concat([rows_for(fold) for fold in train_folds]), rows_for(holdout_fold).reset_index(drop=True)
    holdout, model = _fit_scores(train, holdout)
    simulation = simulate_top_quantile(holdout, round_trip_cost_bps=cost_bps)
    adequate = simulation["summary"].get("sample_adequate", False)
    return {"study": "BEAR-regime candidate economic validation", "generated_at": datetime.now(timezone.utc).isoformat(), "status": "RESEARCH_ONLY" if adequate else "INSUFFICIENT_ECONOMIC_SAMPLE", "data_gate": gate, "model": model, "cost_assumptions": {"round_trip_cost_bps": cost_bps, "horizon_days": HORIZON_DAYS, "top_quantile": TOP_QUANTILE}, "sample": {"train_rows": len(train), "holdout_rows": len(holdout), "holdout_days": int(holdout["date"].nunique()), "skipped_symbols": skipped}, "simulation": simulation, "interpretation": "Held-out BEAR paper simulation only; it does not establish capacity, fill quality, or permission to trade. At least 24 non-overlapping periods are required before annualized metrics are shown."}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the BEAR candidate after turnover costs.")
    parser.add_argument("--cost-bps", type=float, default=ROUND_TRIP_COST_BPS)
    parser.add_argument("--symbols", default="")
    parser.add_argument("--output", type=Path, default=Path("data/research/regime_bear_economic_validation.json"))
    args = parser.parse_args()
    report = build_report([item.strip().upper() for item in args.symbols.split(",") if item.strip()] or None, args.cost_bps)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"saved": str(args.output), "status": report["status"], "summary": report.get("simulation", {}).get("summary")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
