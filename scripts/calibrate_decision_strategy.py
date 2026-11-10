from __future__ import annotations

import json
import math
import os
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import NormalDist

from app import paper_simulator as sim
from scripts.compare_recommendations import DEFAULT_SYMBOLS, _load_prepared, _symbols

WALK_FORWARD_FOLDS = int(os.getenv("DECISION_CALIBRATION_FOLDS", "4"))
WALK_FORWARD_WINDOW_DAYS = int(os.getenv("DECISION_CALIBRATION_WINDOW_DAYS", "360"))
MIN_TRADES_PER_FOLD = int(os.getenv("DECISION_CALIBRATION_MIN_TRADES_PER_FOLD", "3"))
EMBARGO_DAYS = int(os.getenv("DECISION_CALIBRATION_EMBARGO_DAYS", "15"))


@dataclass(frozen=True)
class StrategyParams:
    min_score: int
    min_volume_ratio: float
    max_volatility: float
    stop_atr: float
    target_atr: float
    weak_score: int
    max_positions: int


def _grid() -> list[StrategyParams]:
    rows = []
    for min_score in [62, 66, 70, 74]:
        for min_volume_ratio in [0.7, 0.85, 1.0]:
            for max_volatility in [70, 90, 120]:
                for stop_atr in [1.2, 1.5]:
                    for target_atr in [1.8, 2.3]:
                        for weak_score in [42, 50]:
                            rows.append(
                                StrategyParams(
                                    min_score=min_score,
                                    min_volume_ratio=min_volume_ratio,
                                    max_volatility=max_volatility,
                                    stop_atr=stop_atr,
                                    target_atr=target_atr,
                                    weak_score=weak_score,
                                    max_positions=4,
                                )
                            )
    return rows


def _entry_ok(data: dict, benchmark: dict | None, i: int, params: StrategyParams) -> tuple[bool, int, dict]:
    score, details = sim._opportunity_score(data, i, benchmark)
    if details["market"]["state"] == "risk_off":
        return False, score, details
    if score < params.min_score:
        return False, score, details
    if not sim._buy_base(data, i):
        return False, score, details
    if float(data["volume_ratio"].iloc[i]) < params.min_volume_ratio:
        return False, score, details
    if float(data["annualized_volatility"].iloc[i]) > params.max_volatility:
        return False, score, details
    return True, score, details


def _metrics(state: dict, daily_values: list[dict], capital: float) -> dict:
    final_value = daily_values[-1]["value"] if daily_values else capital
    wins = [trade for trade in state["closed_trades"] if float(trade["pnl"]) > 0]
    losses = [trade for trade in state["closed_trades"] if float(trade["pnl"]) < 0]
    gross_profit = sum(float(trade["pnl"]) for trade in wins)
    gross_loss = abs(sum(float(trade["pnl"]) for trade in losses))
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
    }


def replay(prepared: dict, benchmark: dict | None, capital: float, start: int, end: int, params: StrategyParams) -> dict:
    state = {"cash": capital, "initial_capital": capital, "positions": {}, "closed_trades": []}
    events = []
    daily_values = []

    for i in range(start, end):
        day = str(next(iter(prepared.values()))["history"].index[i].date())
        for symbol, position in list(state["positions"].items()):
            data = prepared[symbol]
            price = float(data["history"]["close"].iloc[i])
            atr = float(data["atr"].iloc[i])
            shares = int(position["shares"])
            position["stop"] = round(max(float(position["stop"]), price - atr * params.stop_atr), 2)
            reason = ""
            if price <= float(position["stop"]):
                reason = "stop_movel"
            elif price >= float(position["target"]) and not position.get("partial_taken"):
                sell_shares = max(1, shares // 2)
                execution_price = sim._sell_execution(price)
                gross = execution_price * sell_shares
                fee = sim._fee(gross)
                pnl = round((execution_price - float(position["entry_price"])) * sell_shares - fee, 2)
                state["cash"] = round(float(state["cash"]) + gross - fee, 2)
                position["shares"] = shares - sell_shares
                position["partial_taken"] = True
                position["stop"] = round(max(float(position["stop"]), float(position["entry_price"])), 2)
                events.append({"day": day, "type": "partial_sell", "symbol": symbol, "pnl": pnl})
                continue
            elif sim._sell_base(data, i):
                reason = "virada_tendencia"
            else:
                score, _ = sim._opportunity_score(data, i, benchmark)
                if score < params.weak_score:
                    reason = "score_fraco"
            if not reason:
                continue
            execution_price = sim._sell_execution(price)
            gross = execution_price * shares
            fee = sim._fee(gross)
            pnl = round((execution_price - float(position["entry_price"])) * shares - fee, 2)
            state["cash"] = round(float(state["cash"]) + gross - fee, 2)
            state["closed_trades"].append({**position, "exit_at": day, "exit_price": round(execution_price, 2), "exit_reason": reason, "pnl": pnl})
            del state["positions"][symbol]
            events.append({"day": day, "type": "sell", "symbol": symbol, "pnl": pnl, "reason": reason})

        ranked = []
        for symbol, data in prepared.items():
            if symbol in state["positions"] or not sim._indicators_ready(data, i):
                continue
            ok, score, details = _entry_ok(data, benchmark, i, params)
            if ok:
                ranked.append((score, float(data["volume_ratio"].iloc[i]), symbol, data, details))
        ranked.sort(reverse=True)
        for score, _, symbol, data, details in ranked:
            if len(state["positions"]) >= params.max_positions:
                break
            price = float(data["history"]["close"].iloc[i])
            atr = float(data["atr"].iloc[i])
            market = sim._market_regime(benchmark, i)
            budget = min(float(state["cash"]), capital * sim.MAX_POSITION_PCT * float(market["risk_multiplier"]))
            execution_price = sim._buy_execution(price)
            shares = int(budget // (execution_price * (1 + sim.COST_BPS / 10000)))
            if shares <= 0:
                continue
            gross = shares * execution_price
            fee = sim._fee(gross)
            state["cash"] = round(float(state["cash"]) - gross - fee, 2)
            state["positions"][symbol] = {
                "symbol": symbol,
                "entry_at": day,
                "entry_price": round(execution_price, 2),
                "shares": shares,
                "stop": round(execution_price - atr * params.stop_atr, 2),
                "target": round(execution_price + atr * params.target_atr, 2),
                "score": score,
                "score_details": details,
            }
            events.append({"day": day, "type": "buy", "symbol": symbol, "score": score})

        daily_values.append({"day": day, "value": sim._portfolio_value_at(state, prepared, i)})

    result = _metrics(state, daily_values, capital)
    result.update(
        {
            "buys": sum(1 for event in events if event["type"] == "buy"),
            "sells": sum(1 for event in events if event["type"] == "sell"),
            "partial_sells": sum(1 for event in events if event["type"] == "partial_sell"),
            "open_positions": state["positions"],
            "events": events[-80:],
            "daily_values": daily_values[-80:],
        }
    )
    return result


def _rank_result(metrics: dict) -> float:
    trade_penalty = 5 if metrics["closed_trades"] < 8 else 0
    drawdown_penalty = abs(min(0, metrics["max_drawdown_pct"])) * 0.7
    pf_bonus = min(8, max(0, metrics["profit_factor"] - 1) * 5) if metrics["profit_factor"] != 999 else 8
    return metrics["return_pct"] + pf_bonus - drawdown_penalty - trade_penalty


def _walk_forward_folds(
    max_len: int, num_folds: int, window_days: int, min_start: int, embargo_days: int = EMBARGO_DAYS
) -> list[tuple[int, int]]:
    """Splits the available history into `num_folds` contiguous, walking-forward
    windows (oldest first), each candidate scored on every fold independently
    — a config only looks good if it holds up across several different
    market periods, not just the one window it happened to be picked on.

    `embargo_days` skips that many samples right after each fold boundary
    (except the very first fold). Indicators like SMA200/ATR look backward
    over 14-200 days, so a sample right at the start of fold k+1 shares
    almost all of its lookback window with the last sample of fold k — an
    embargo removes that near-duplicate stretch so consecutive folds are
    closer to independent evidence, not just "the next day" wearing a new
    label. See Bailey & López de Prado on purging/embargo in walk-forward
    and cross-validation.
    """
    total_start = max(min_start, max_len - window_days)
    total_len = max_len - total_start
    fold_len = max(10 + embargo_days, total_len // num_folds)
    folds = []
    for k in range(num_folds):
        raw_start = total_start + k * fold_len
        start = raw_start + embargo_days if k > 0 else raw_start
        end = total_start + (k + 1) * fold_len if k < num_folds - 1 else max_len
        if end - start >= 10:
            folds.append((start, end))
    return folds


def _walk_forward_rank(fold_metrics: list[dict]) -> dict:
    """Aggregates per-fold performance into one robustness score.

    Rewards a high average across folds, but penalizes inconsistency (std of
    per-fold rank) and a bad worst-case fold explicitly — this is what
    exposes a config that only worked because of a single lucky window
    (the exact failure mode found in the previous single train/test split).
    """
    fold_ranks = [_rank_result(metrics) for metrics in fold_metrics]
    mean_rank = statistics.mean(fold_ranks)
    worst_rank = min(fold_ranks)
    std_rank = statistics.pstdev(fold_ranks) if len(fold_ranks) > 1 else 0.0
    losing_folds = sum(1 for metrics in fold_metrics if metrics["return_pct"] < 0)
    score = mean_rank - std_rank * 0.6 - max(0, -worst_rank) * 0.4 - losing_folds * 3
    fold_sharpes = [metrics["sharpe_ratio"] for metrics in fold_metrics if metrics.get("sharpe_ratio") is not None]
    mean_sharpe = statistics.mean(fold_sharpes) if fold_sharpes else None
    return {
        "mean_rank": round(mean_rank, 4),
        "worst_fold_rank": round(worst_rank, 4),
        "std_rank": round(std_rank, 4),
        "losing_folds": losing_folds,
        "walk_forward_rank": round(score, 4),
        "mean_sharpe": round(mean_sharpe, 4) if mean_sharpe is not None else None,
        # Only a positive rank with at most one bad fold gets to override the
        # live decision engine's static thresholds (see
        # app.decision_engine.reload_calibration) — anything else stays on
        # hand-picked defaults instead of trading on an unvalidated config.
        # main() may still downgrade this to False after checking the
        # deflated Sharpe ratio across all tested configs.
        "reliable": bool(score > 0 and losing_folds <= 1),
    }


def deflated_sharpe_ratio(candidate_sharpes: list[float], best_sharpe: float, track_length: int) -> dict:
    """Corrects the best Sharpe ratio found across N tested configs for
    selection bias (Bailey & Lopez de Prado, 2014, "The Deflated Sharpe
    Ratio"). Testing hundreds of parameter combinations means the single
    best-looking one is expected to look good partly by chance alone — DSR
    estimates the probability its true Sharpe ratio is actually positive
    once that multiple-testing effect is priced in. Approximation: treats
    returns as normal (no skew/kurtosis correction) and uses the surviving
    candidates' own Sharpe distribution as the trial set, since exhaustively
    tracking every combination attempted (including ones dropped for too few
    trades) isn't currently kept.
    """
    n = len(candidate_sharpes)
    if n < 2 or track_length < 3:
        return {"deflated_sharpe_ratio": None, "expected_max_sharpe_by_chance": None, "trials": n}
    mean_sr = statistics.mean(candidate_sharpes)
    std_sr = statistics.pstdev(candidate_sharpes)
    if std_sr == 0:
        return {"deflated_sharpe_ratio": None, "expected_max_sharpe_by_chance": None, "trials": n}
    euler_mascheroni = 0.5772156649
    dist = NormalDist()
    expected_max_sr = mean_sr + std_sr * (
        (1 - euler_mascheroni) * dist.inv_cdf(1 - 1 / n) + euler_mascheroni * dist.inv_cdf(1 - 1 / (n * math.e))
    )
    se_sr = (1 / max(1, track_length - 1)) ** 0.5
    z = (best_sharpe - expected_max_sr) / se_sr if se_sr > 0 else None
    dsr = dist.cdf(z) if z is not None else None
    return {
        "deflated_sharpe_ratio": round(dsr, 4) if dsr is not None else None,
        "expected_max_sharpe_by_chance": round(expected_max_sr, 4),
        "trials": n,
    }


def _compact(metrics: dict) -> dict:
    keys = [
        "final_value",
        "return_pct",
        "closed_trades",
        "win_rate_pct",
        "profit_factor",
        "sharpe_ratio",
        "sortino_ratio",
        "max_drawdown_pct",
        "gross_profit",
        "gross_loss",
        "buys",
        "sells",
        "partial_sells",
    ]
    return {key: metrics[key] for key in keys if key in metrics}


def _compact_row(row: dict) -> dict:
    return {
        "params": row["params"],
        "folds": [_compact(metrics) for metrics in row["folds"]],
        **row["walk_forward"],
    }


def main() -> None:
    capital = float(os.getenv("PAPER_SIM_INITIAL_CAPITAL", "10000"))
    symbols = _symbols() or DEFAULT_SYMBOLS
    prepared, benchmark, skipped = _load_prepared(symbols)
    max_len = min(len(data["history"]) for data in prepared.values())
    folds = _walk_forward_folds(max_len, WALK_FORWARD_FOLDS, WALK_FORWARD_WINDOW_DAYS, min_start=65)

    candidates = []
    for params in _grid():
        fold_metrics = [replay(prepared, benchmark, capital, start, end, params) for start, end in folds]
        valid_folds = sum(1 for metrics in fold_metrics if metrics["closed_trades"] >= MIN_TRADES_PER_FOLD)
        if valid_folds < len(folds) - 1:
            continue
        walk_forward = _walk_forward_rank(fold_metrics)
        candidates.append({"params": asdict(params), "folds": fold_metrics, "walk_forward": walk_forward})

    candidates.sort(key=lambda row: row["walk_forward"]["walk_forward_rank"], reverse=True)
    best = candidates[0] if candidates else None

    track_length = sum(end - start for start, end in folds)
    candidate_sharpes = [row["walk_forward"]["mean_sharpe"] for row in candidates if row["walk_forward"]["mean_sharpe"] is not None]
    dsr_analysis = {"deflated_sharpe_ratio": None, "expected_max_sharpe_by_chance": None, "trials": len(candidate_sharpes)}
    dsr_threshold = float(os.getenv("DECISION_CALIBRATION_DSR_THRESHOLD", "0.95"))
    if best is not None and best["walk_forward"]["mean_sharpe"] is not None:
        dsr_analysis = deflated_sharpe_ratio(candidate_sharpes, best["walk_forward"]["mean_sharpe"], track_length)
        dsr = dsr_analysis["deflated_sharpe_ratio"]
        if dsr is not None and dsr < dsr_threshold and best["walk_forward"]["reliable"]:
            # The raw walk-forward rank looked positive, but after correcting
            # for how many configs we tried (selection bias), the best
            # Sharpe isn't distinguishable from what pure luck would produce
            # across this many trials — do not let the live engine trade on it.
            best["walk_forward"]["reliable"] = False
            best["walk_forward"]["reliable_reason"] = (
                f"Rank walk-forward positivo, mas Deflated Sharpe Ratio {dsr:.3f} < "
                f"{dsr_threshold} apos corrigir para {len(candidate_sharpes)} configuracoes testadas."
            )

    result = {
        "capital": capital,
        "symbols": sorted(prepared),
        "skipped": skipped,
        "folds": [{"start_index": start, "end_index": end} for start, end in folds],
        "tested_configs": len(candidates),
        "embargo_days": EMBARGO_DAYS,
        "method": (
            f"Walk-forward: cada configuracao roda em {len(folds)} janelas historicas nao "
            f"sobrepostas (com {EMBARGO_DAYS} dias de embargo entre elas) e so e considerada boa "
            "se for consistente entre elas E se o Sharpe Ratio sobreviver a correcao por teste "
            "multiplo (Deflated Sharpe Ratio) sobre as configuracoes testadas."
        ),
        "deflated_sharpe_ratio_analysis": {**dsr_analysis, "threshold": dsr_threshold},
        "best": _compact_row(best) if best else None,
        "top_10": [_compact_row(row) for row in candidates[:10]],
    }
    path = Path(os.getenv("DECISION_CALIBRATION_PATH", "data/decision_strategy_calibration.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
