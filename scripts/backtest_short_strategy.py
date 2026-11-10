"""Backtests and walk-forward calibrates the short-side rule engine
(app.decision_engine's SELL_SHORT / WATCH_SHORT logic) with fictitious
capital.

Two things this does, both mirroring the long-side machinery so short gets
the same rigor instead of hand-picked defaults copied from the long side:

1. `replay()` — the mirror of scripts.calibrate_decision_strategy.replay,
   inverted for short P&L (profit when price falls). Reuses the exact same
   StrategyParams shape so both sides can be grid-searched identically.
2. `main()` — walk-forward calibration (same folds/embargo/DSR gate as
   scripts.calibrate_decision_strategy) over the short-side grid, writing
   short_strategy_calibration.json for app.decision_engine to read.

Run as `python -m scripts.backtest_short_strategy` for the walk-forward
calibration, or import `replay()` directly (as validate scripts do) for a
one-off backtest with the current static DECISION_SHORT_* thresholds.
"""
from __future__ import annotations

import json
import os
import statistics
from dataclasses import asdict
from pathlib import Path

from app import decision_engine as de
from app import paper_simulator as sim
from scripts.calibrate_decision_strategy import (
    EMBARGO_DAYS,
    MIN_TRADES_PER_FOLD,
    WALK_FORWARD_FOLDS,
    WALK_FORWARD_WINDOW_DAYS,
    StrategyParams,
    _rank_result,
    _walk_forward_folds,
    _walk_forward_rank,
    deflated_sharpe_ratio,
)
from scripts.compare_recommendations import DEFAULT_SYMBOLS, _load_prepared, _symbols

RESULT_PATH = Path(os.getenv("SHORT_BACKTEST_PATH", "data/short_strategy_backtest.json"))
CALIBRATION_PATH = Path(os.getenv("SHORT_CALIBRATION_PATH", "data/short_strategy_calibration.json"))


def _grid() -> list[StrategyParams]:
    rows = []
    for min_score in [62, 70, 78]:
        for min_volume_ratio in [0.85, 1.1]:
            for max_volatility in [70, 100]:
                for stop_atr in [1.2, 1.5]:
                    for target_atr in [1.8, 2.3]:
                        rows.append(
                            StrategyParams(
                                min_score=min_score,
                                min_volume_ratio=min_volume_ratio,
                                max_volatility=max_volatility,
                                stop_atr=stop_atr,
                                target_atr=target_atr,
                                weak_score=42,
                                max_positions=4,
                            )
                        )
    return rows


def _entry_ok(data: dict, i: int, benchmark: dict | None, params: StrategyParams) -> tuple[bool, int, dict]:
    if not sim._indicators_ready(data, i) or not sim._sell_base(data, i):
        return False, 0, {}
    score, details = de._bearish_score(data, i, benchmark)
    if score < params.min_score:
        return False, score, details
    if float(data["volume_ratio"].iloc[i]) < params.min_volume_ratio:
        return False, score, details
    if float(data["annualized_volatility"].iloc[i]) > params.max_volatility:
        return False, score, details
    return True, score, details


def replay(prepared: dict, benchmark: dict | None, capital: float, start: int, end: int, params: StrategyParams) -> dict:
    state = {"cash": capital, "initial_capital": capital, "positions": {}, "closed_trades": []}
    events: list[dict] = []
    daily_values: list[dict] = []

    for i in range(start, end):
        day = str(next(iter(prepared.values()))["history"].index[i].date())

        for symbol, position in list(state["positions"].items()):
            data = prepared[symbol]
            price = float(data["history"]["close"].iloc[i])
            atr = float(data["atr"].iloc[i])
            shares = int(position["shares"])
            position["stop"] = round(min(float(position["stop"]), price + atr * params.stop_atr), 2)
            reason = ""
            if price >= float(position["stop"]):
                reason = "stop_hit"
            elif price <= float(position["target"]) and not position.get("partial_taken"):
                cover_shares = max(1, shares // 2)
                execution_price = sim._buy_execution(price)
                fee = sim._fee(execution_price * cover_shares)
                pnl = round((float(position["entry_price"]) - execution_price) * cover_shares - fee, 2)
                state["cash"] = round(float(state["cash"]) + pnl, 2)
                position["shares"] = shares - cover_shares
                position["partial_taken"] = True
                position["stop"] = round(min(float(position["stop"]), float(position["entry_price"])), 2)
                events.append({"day": day, "type": "partial_cover", "symbol": symbol, "pnl": pnl})
                if int(position["shares"]) > 0:
                    continue
                reason = "target_hit"
            elif sim._buy_base(data, i):
                reason = "trend_flip"
            else:
                score, _ = de._bearish_score(data, i, benchmark)
                if score < params.weak_score:
                    reason = "score_fraco"
            if not reason:
                continue
            execution_price = sim._buy_execution(price)
            fee = sim._fee(execution_price * shares)
            pnl = round((float(position["entry_price"]) - execution_price) * shares - fee, 2)
            state["cash"] = round(float(state["cash"]) + pnl, 2)
            state["closed_trades"].append({**position, "exit_at": day, "exit_price": round(execution_price, 2), "exit_reason": reason, "pnl": pnl})
            del state["positions"][symbol]
            events.append({"day": day, "type": "cover", "symbol": symbol, "pnl": pnl, "reason": reason})

        ranked = []
        for symbol, data in prepared.items():
            if symbol in state["positions"]:
                continue
            ok, score, details = _entry_ok(data, i, benchmark, params)
            if ok:
                ranked.append((score, symbol, data, details))
        ranked.sort(reverse=True)
        for score, symbol, data, details in ranked:
            if len(state["positions"]) >= params.max_positions:
                break
            price = float(data["history"]["close"].iloc[i])
            atr = float(data["atr"].iloc[i])
            market = details["market"]
            budget = min(float(state["cash"]), capital * sim.MAX_POSITION_PCT * float(market.get("risk_multiplier", 0.7)))
            execution_price = sim._sell_execution(price)
            shares = int(budget // (execution_price * (1 + sim.COST_BPS / 10000)))
            if shares <= 0:
                continue
            state["positions"][symbol] = {
                "symbol": symbol,
                "entry_at": day,
                "entry_price": round(execution_price, 2),
                "shares": shares,
                "stop": round(execution_price + atr * params.stop_atr, 2),
                "target": round(execution_price - atr * params.target_atr, 2),
                "score": score,
            }
            events.append({"day": day, "type": "short", "symbol": symbol, "score": score})

        value = float(state["cash"])
        for symbol, position in state["positions"].items():
            data = prepared[symbol]
            if i < len(data["history"]):
                price = float(data["history"]["close"].iloc[i])
                value += (float(position["entry_price"]) - price) * float(position["shares"])
        daily_values.append({"day": day, "value": round(value, 2)})

    final_value = daily_values[-1]["value"] if daily_values else capital
    wins = [t for t in state["closed_trades"] if float(t["pnl"]) > 0]
    losses = [t for t in state["closed_trades"] if float(t["pnl"]) < 0]
    gross_profit = sum(float(t["pnl"]) for t in wins)
    gross_loss = abs(sum(float(t["pnl"]) for t in losses))
    peak = capital
    max_drawdown = 0.0
    for row in daily_values:
        peak = max(peak, float(row["value"]))
        if peak:
            max_drawdown = min(max_drawdown, (float(row["value"]) / peak - 1) * 100)

    return {
        "final_value": round(final_value, 2),
        "return_pct": round((final_value / capital - 1) * 100, 2),
        "closed_trades": len(state["closed_trades"]),
        "win_rate_pct": round(len(wins) / len(state["closed_trades"]) * 100, 2) if state["closed_trades"] else 0,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else (999 if gross_profit > 0 else 0),
        **sim.risk_adjusted_metrics(daily_values),
        "max_drawdown_pct": round(max_drawdown, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "events": events[-80:],
        "daily_values": daily_values[-80:],
    }


def _compact(metrics: dict) -> dict:
    keys = ["final_value", "return_pct", "closed_trades", "win_rate_pct", "profit_factor", "sharpe_ratio", "sortino_ratio", "max_drawdown_pct", "gross_profit", "gross_loss"]
    return {key: metrics[key] for key in keys if key in metrics}


def _compact_row(row: dict) -> dict:
    return {"params": row["params"], "folds": [_compact(m) for m in row["folds"]], **row["walk_forward"]}


def main() -> None:
    capital = float(os.getenv("PAPER_SIM_INITIAL_CAPITAL", "10000"))
    symbols = _symbols() or DEFAULT_SYMBOLS
    prepared, benchmark, skipped = _load_prepared(symbols)
    max_len = min(len(data["history"]) for data in prepared.values())
    folds = _walk_forward_folds(max_len, WALK_FORWARD_FOLDS, WALK_FORWARD_WINDOW_DAYS, min_start=65, embargo_days=EMBARGO_DAYS)

    candidates = []
    for params in _grid():
        fold_metrics = [replay(prepared, benchmark, capital, start, end, params) for start, end in folds]
        valid_folds = sum(1 for m in fold_metrics if m["closed_trades"] >= MIN_TRADES_PER_FOLD)
        if valid_folds < len(folds) - 1:
            continue
        walk_forward = _walk_forward_rank(fold_metrics)
        candidates.append({"params": asdict(params), "folds": fold_metrics, "walk_forward": walk_forward})

    candidates.sort(key=lambda row: row["walk_forward"]["walk_forward_rank"], reverse=True)
    best = candidates[0] if candidates else None

    track_length = sum(end - start for start, end in folds)
    candidate_sharpes = [row["walk_forward"]["mean_sharpe"] for row in candidates if row["walk_forward"]["mean_sharpe"] is not None]
    dsr_threshold = float(os.getenv("DECISION_CALIBRATION_DSR_THRESHOLD", "0.95"))
    dsr_analysis = {"deflated_sharpe_ratio": None, "expected_max_sharpe_by_chance": None, "trials": len(candidate_sharpes)}
    if best is not None and best["walk_forward"]["mean_sharpe"] is not None:
        dsr_analysis = deflated_sharpe_ratio(candidate_sharpes, best["walk_forward"]["mean_sharpe"], track_length)
        dsr = dsr_analysis["deflated_sharpe_ratio"]
        if dsr is not None and dsr < dsr_threshold and best["walk_forward"]["reliable"]:
            best["walk_forward"]["reliable"] = False
            best["walk_forward"]["reliable_reason"] = (
                f"Rank walk-forward positivo, mas Deflated Sharpe Ratio {dsr:.3f} < {dsr_threshold} "
                f"apos corrigir para {len(candidate_sharpes)} configuracoes testadas."
            )

    result = {
        "capital": capital,
        "symbols": sorted(prepared),
        "skipped": skipped,
        "folds": [{"start_index": s, "end_index": e} for s, e in folds],
        "embargo_days": EMBARGO_DAYS,
        "tested_configs": len(candidates),
        "deflated_sharpe_ratio_analysis": {**dsr_analysis, "threshold": dsr_threshold},
        "best": _compact_row(best) if best else None,
        "top_10": [_compact_row(row) for row in candidates[:10]],
    }
    CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    CALIBRATION_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nCalibracao short salva em {CALIBRATION_PATH}")


if __name__ == "__main__":
    main()
