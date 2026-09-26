from __future__ import annotations

import json
import os
from pathlib import Path

from app import paper_simulator as sim

DEFAULT_SYMBOLS = sim.DEFAULT_SYMBOLS


def _symbols() -> list[str]:
    raw = os.getenv("PAPER_SIM_SYMBOLS", "")
    if raw:
        return [symbol.strip().upper() for symbol in raw.split(",") if symbol.strip()]
    return DEFAULT_SYMBOLS


def _load_prepared(symbols: list[str]) -> tuple[dict, dict | None, list[str]]:
    prepared = {}
    skipped = []
    benchmark = sim.benchmark_context()
    for symbol in symbols:
        history = sim._history(symbol)
        if history.empty or len(history) < 120:
            skipped.append(symbol)
            continue
        prepared[symbol] = sim._prepared(history)
    return prepared, benchmark, skipped


def _value_at(state: dict, prepared: dict, i: int) -> float:
    return sim._portfolio_value_at(state, prepared, i)


def _codex_entry_ok(data: dict, i: int, benchmark: dict | None) -> tuple[bool, int, dict]:
    score, details = sim._opportunity_score(data, i, benchmark)
    market = details["market"]
    if market["state"] == "risk_off":
        return False, score, details
    if score < 66:
        return False, score, details
    if not sim._buy_base(data, i):
        return False, score, details
    if float(data["volume_ratio"].iloc[i]) < 0.85:
        return False, score, details
    if float(data["annualized_volatility"].iloc[i]) > 110:
        return False, score, details
    return True, score, details


def _codex_exit_reason(data: dict, i: int, position: dict) -> str:
    price = float(data["history"]["close"].iloc[i])
    atr = float(data["atr"].iloc[i])
    position["stop"] = round(max(float(position["stop"]), price - atr * 1.4), 2)
    if price <= float(position["stop"]):
        return "stop_movel"
    if price >= float(position["target"]) and not position.get("partial_taken"):
        return "alvo_parcial"
    if sim._sell_base(data, i):
        return "virada_tendencia"
    score, details = sim._opportunity_score(data, i, None)
    if score < 48:
        return "score_fraco"
    return ""


def codex_replay(prepared: dict, benchmark: dict | None, capital: float, days: int) -> dict:
    max_len = min(len(data["history"]) for data in prepared.values())
    start = max(65, max_len - days)
    state = {"cash": capital, "initial_capital": capital, "positions": {}, "closed_trades": []}
    events = []
    daily_values = []

    for i in range(start, max_len):
        day = str(next(iter(prepared.values()))["history"].index[i].date())

        for symbol, position in list(state["positions"].items()):
            data = prepared[symbol]
            price = float(data["history"]["close"].iloc[i])
            shares = int(position["shares"])
            reason = _codex_exit_reason(data, i, position)
            if reason == "alvo_parcial":
                sell_shares = max(1, shares // 2)
                execution_price = sim._sell_execution(price)
                gross = execution_price * sell_shares
                fee = sim._fee(gross)
                pnl = round((execution_price - float(position["entry_price"])) * sell_shares - fee, 2)
                state["cash"] = round(float(state["cash"]) + gross - fee, 2)
                position["shares"] = shares - sell_shares
                position["partial_taken"] = True
                position["stop"] = round(max(float(position["stop"]), float(position["entry_price"])), 2)
                events.append({"day": day, "type": "partial_sell", "symbol": symbol, "shares": sell_shares, "price": round(execution_price, 2), "pnl": pnl, "reason": reason})
                continue
            if not reason:
                continue
            execution_price = sim._sell_execution(price)
            gross = execution_price * shares
            fee = sim._fee(gross)
            pnl = round((execution_price - float(position["entry_price"])) * shares - fee, 2)
            state["cash"] = round(float(state["cash"]) + gross - fee, 2)
            closed = {**position, "exit_at": day, "exit_price": round(execution_price, 2), "exit_reason": reason, "pnl": pnl}
            state["closed_trades"].append(closed)
            del state["positions"][symbol]
            events.append({"day": day, "type": "sell", "symbol": symbol, "shares": shares, "price": round(execution_price, 2), "pnl": pnl, "reason": reason})

        ranked = []
        for symbol, data in prepared.items():
            if symbol in state["positions"] or not sim._indicators_ready(data, i):
                continue
            ok, score, details = _codex_entry_ok(data, i, benchmark)
            if ok:
                ranked.append((score, float(data["volume_ratio"].iloc[i]), symbol, data, details))
        ranked.sort(reverse=True)

        for score, _, symbol, data, details in ranked:
            if len(state["positions"]) >= sim.MAX_OPEN_POSITIONS:
                break
            market = sim._market_regime(benchmark, i)
            price = float(data["history"]["close"].iloc[i])
            execution_price = sim._buy_execution(price)
            budget = min(float(state["cash"]), capital * sim.MAX_POSITION_PCT * float(market["risk_multiplier"]))
            shares = int(budget // (execution_price * (1 + sim.COST_BPS / 10000)))
            if shares <= 0:
                continue
            atr = float(data["atr"].iloc[i])
            gross = shares * execution_price
            fee = sim._fee(gross)
            state["cash"] = round(float(state["cash"]) - gross - fee, 2)
            state["positions"][symbol] = {
                "symbol": symbol,
                "entry_at": day,
                "entry_price": round(execution_price, 2),
                "shares": shares,
                "stop": round(execution_price - atr * 1.4, 2),
                "target": round(execution_price + atr * 2.0, 2),
                "score": score,
                "score_details": details,
                "buy_fee": round(fee, 2),
            }
            events.append({"day": day, "type": "buy", "symbol": symbol, "shares": shares, "price": round(execution_price, 2), "cost": round(gross + fee, 2), "score": score})

        daily_values.append({"day": day, "value": _value_at(state, prepared, i)})

    final_value = daily_values[-1]["value"] if daily_values else capital
    wins = [trade for trade in state["closed_trades"] if float(trade["pnl"]) > 0]
    losses = [trade for trade in state["closed_trades"] if float(trade["pnl"]) < 0]
    gross_profit = sum(float(trade["pnl"]) for trade in wins)
    gross_loss = abs(sum(float(trade["pnl"]) for trade in losses))
    peak = capital
    max_drawdown = 0.0
    for row in daily_values:
        peak = max(peak, float(row["value"]))
        max_drawdown = min(max_drawdown, (float(row["value"]) / peak - 1) * 100)

    return {
        "final_value": round(final_value, 2),
        "return_pct": round((final_value / capital - 1) * 100, 2),
        "buys": sum(1 for event in events if event["type"] == "buy"),
        "sells": sum(1 for event in events if event["type"] == "sell"),
        "partial_sells": sum(1 for event in events if event["type"] == "partial_sell"),
        "closed_trades": len(state["closed_trades"]),
        "win_rate_pct": round(len(wins) / len(state["closed_trades"]) * 100, 2) if state["closed_trades"] else 0,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else (999 if gross_profit > 0 else 0),
        "max_drawdown_pct": round(max_drawdown, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "cash": round(float(state["cash"]), 2),
        "open_positions": state["positions"],
        "events": events[-120:],
        "daily_values": daily_values[-120:],
    }


def current_recommendations(prepared: dict, benchmark: dict | None) -> list[dict]:
    rows = []
    for symbol, data in prepared.items():
        i = len(data["history"]) - 1
        if not sim._indicators_ready(data, i):
            continue
        ok, score, details = _codex_entry_ok(data, i, benchmark)
        price = float(data["history"]["close"].iloc[i])
        rows.append(
            {
                "symbol": symbol,
                "price": round(price, 2),
                "codex_score": score,
                "codex_action": "BUY" if ok else "WAIT",
                "market": details["market"]["state"],
                "volume_ratio": round(float(data["volume_ratio"].iloc[i]), 2),
                "rsi": round(float(data["rsi"].iloc[i]), 2),
                "annualized_volatility": round(float(data["annualized_volatility"].iloc[i]), 2),
                "atr_pct": details["atr_pct"],
            }
        )
    return sorted(rows, key=lambda row: row["codex_score"], reverse=True)


def main() -> None:
    capital = float(os.getenv("PAPER_SIM_INITIAL_CAPITAL", "10000"))
    days = int(os.getenv("PAPER_SIM_REPLAY_DAYS", "180"))
    symbols = _symbols()
    prepared, benchmark, skipped = _load_prepared(symbols)

    ai_result = sim.run_deep_replay(initial_capital=capital, replay_days=days)
    codex_result = codex_replay(prepared, benchmark, capital, days)
    recommendations = current_recommendations(prepared, benchmark)

    result = {
        "capital": capital,
        "days": days,
        "symbols": sorted(prepared),
        "skipped": skipped,
        "ai_project_strategy": {
            key: ai_result.get(key)
            for key in [
                "final_value",
                "return_pct",
                "buys",
                "sells",
                "partial_sells",
                "closed_trades",
                "win_rate_pct",
                "profit_factor",
                "max_drawdown_pct",
                "last_calibration",
            ]
        },
        "codex_strategy": codex_result,
        "current_recommendations": recommendations,
    }
    path = Path(os.getenv("RECOMMENDATION_COMPARISON_PATH", "data/recommendation_comparison.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
