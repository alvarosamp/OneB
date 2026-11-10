"""Simple walk-forward backtest for a (possibly compound) alert rule.

Not a full backtesting engine — just answers "how many times would this
rule have fired over this history, and what happened N bars afterward on
average?". Reuses the exact same evaluate_conditions() used live, so the
backtest result matches real behavior by construction.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.models import RuleLogic
from app.rules_engine import MarketState, RuleContext, evaluate_conditions

_MIN_LOOKBACK = 30  # bars needed before indicators like EMA21/MACD have real values


@dataclass
class BacktestOccurrence:
    date: str
    price: float
    forward_return_pct: float | None


@dataclass
class BacktestResult:
    trigger_count: int
    avg_forward_return_pct: float | None
    occurrences: list[BacktestOccurrence] = field(default_factory=list)
    win_rate_pct: float | None = None
    profit_factor: float | None = None
    max_drawdown_pct: float | None = None
    buy_hold_return_pct: float | None = None


def backtest_conditions(
    conditions: list[RuleContext],
    logic: RuleLogic,
    history: pd.DataFrame,
    symbol: str = "",
    forward_bars: int = 5,
    max_occurrences: int = 30,
) -> BacktestResult:
    if history.empty or not conditions:
        return BacktestResult(trigger_count=0, avg_forward_return_pct=None, occurrences=[])

    close = history["close"]
    occurrences: list[BacktestOccurrence] = []

    start = min(_MIN_LOOKBACK, len(history) - 1)
    for i in range(start, len(history)):
        window = history.iloc[: i + 1]
        price = close.iloc[i]
        prev_price = close.iloc[i - 1] if i > 0 else price
        change_pct = ((price - prev_price) / prev_price * 100) if prev_price else 0.0

        state = MarketState(symbol=symbol, price=price, change_pct=change_pct, volume=window["volume"].iloc[-1], history=window)
        result = evaluate_conditions(conditions, logic, state)
        if not result.triggered:
            continue

        forward_return = None
        if i + forward_bars < len(close):
            future_price = close.iloc[i + forward_bars]
            forward_return = ((future_price - price) / price * 100) if price else None

        occurrences.append(
            BacktestOccurrence(
                date=history.index[i].isoformat(),
                price=round(float(price), 2),
                forward_return_pct=round(forward_return, 2) if forward_return is not None else None,
            )
        )

    valid_returns = [o.forward_return_pct for o in occurrences if o.forward_return_pct is not None]
    avg_return = round(sum(valid_returns) / len(valid_returns), 2) if valid_returns else None
    wins = [r for r in valid_returns if r > 0]
    losses = [r for r in valid_returns if r < 0]
    win_rate = round(len(wins) / len(valid_returns) * 100, 2) if valid_returns else None
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss else (999.0 if gross_profit else None)
    equity = close / close.iloc[0] if len(close) else close
    drawdown = ((equity / equity.cummax()) - 1) * 100 if len(equity) else close
    max_drawdown = round(float(drawdown.min()), 2) if len(drawdown) else None
    buy_hold = round(float((close.iloc[-1] / close.iloc[0] - 1) * 100), 2) if len(close) >= 2 else None

    return BacktestResult(
        trigger_count=len(occurrences),
        avg_forward_return_pct=avg_return,
        occurrences=occurrences[-max_occurrences:],
        win_rate_pct=win_rate,
        profit_factor=profit_factor,
        max_drawdown_pct=max_drawdown,
        buy_hold_return_pct=buy_hold,
    )
