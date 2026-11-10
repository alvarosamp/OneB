"""Audit technical indicator setups on Tiingo-backed EOD data.

This is intentionally product-facing: each setup is a candidate playbook for
Mesa Tecnica/Escola, not a black-box model. The script evaluates simple,
auditable rules after costs and slippage, then ranks them by robustness.

Run:
    python -m scripts.audit_indicator_setups
"""
from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from app import indicators
from app.market_data import service as market_data_service
from scripts.compare_recommendations import DEFAULT_SYMBOLS, _symbols

OUT_PATH = Path("data/indicator_setup_audit.json")
PERIOD = "2y"
INTERVAL = "1d"
HOLD_DAYS = 5
ROUND_TRIP_COST_BPS = 20
MIN_SIGNALS = 20


@dataclass(frozen=True)
class Setup:
    name: str
    direction: str
    category: str
    description: str
    signal_fn: Callable[[pd.DataFrame], pd.Series]


def _safe_float(value) -> float | None:
    if value is None or pd.isna(value) or np.isinf(value):
        return None
    return float(value)


def _max_drawdown(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    equity = (1 + returns / 100).cumprod()
    drawdown = equity / equity.cummax() - 1
    return float(drawdown.min() * 100)


def _profit_factor(returns: pd.Series) -> float | None:
    wins = returns[returns > 0].sum()
    losses = abs(returns[returns < 0].sum())
    if losses == 0:
        return 999.0 if wins > 0 else None
    return float(wins / losses)


def _t_stat(values: pd.Series) -> float | None:
    values = values.dropna()
    if len(values) < 3:
        return None
    std = float(values.std())
    if std == 0:
        return None
    return float(values.mean() / std * math.sqrt(len(values)))


def _prep(history: pd.DataFrame) -> pd.DataFrame:
    df = history.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    df["ema20"] = indicators.ema(close, 20)
    df["ema50"] = indicators.ema(close, 50)
    df["ema200"] = indicators.ema(close, 200)
    df["rsi14"] = indicators.rsi(close, 14)
    macd = indicators.macd(close)
    df["macd"] = macd["macd"]
    df["macd_signal"] = macd["signal"]
    df["macd_hist"] = macd["histogram"]
    bb = indicators.bollinger_bands(close)
    df["bb_upper"] = bb["upper"]
    df["bb_lower"] = bb["lower"]
    df["bb_mid"] = bb["mid"]
    df["bb_width_pct"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"].replace(0, np.nan) * 100
    df["bb_width_rank120"] = df["bb_width_pct"].rolling(120, min_periods=60).rank(pct=True)
    df["volume_ratio20"] = indicators.volume_ratio(volume, 20)
    df["atr14"] = indicators.atr(high, low, close, 14)
    adx = indicators.adx(high, low, close, 14)
    df["adx14"] = adx["adx"]
    df["plus_di"] = adx["plus_di"]
    df["minus_di"] = adx["minus_di"]
    df["prior_high20"] = high.rolling(20, min_periods=20).max().shift(1)
    df["prior_low20"] = low.rolling(20, min_periods=20).min().shift(1)
    df["range_pct"] = (high - low) / close * 100
    df["vol20"] = close.pct_change().rolling(20, min_periods=20).std() * math.sqrt(252) * 100
    return df


def _cross_up(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a > b) & (a.shift(1) <= b.shift(1))


def _cross_down(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a < b) & (a.shift(1) >= b.shift(1))


def _setups() -> list[Setup]:
    return [
        Setup(
            "trend_pullback_long",
            "LONG",
            "pullback",
            "Close above EMA50, EMA20 above EMA50, RSI resets to 40-58, then close recovers EMA20.",
            lambda d: (d["close"] > d["ema50"]) & (d["ema20"] > d["ema50"]) & d["rsi14"].between(40, 58) & _cross_up(d["close"], d["ema20"]),
        ),
        Setup(
            "volume_breakout_long",
            "LONG",
            "breakout",
            "20-day breakout with relative volume and ADX confirmation.",
            lambda d: (d["close"] > d["prior_high20"]) & (d["volume_ratio20"] >= 1.2) & (d["adx14"] >= 18),
        ),
        Setup(
            "macd_momentum_long",
            "LONG",
            "momentum",
            "MACD crosses above signal while price is above EMA50 and trend strength is not dead.",
            lambda d: _cross_up(d["macd"], d["macd_signal"]) & (d["close"] > d["ema50"]) & (d["adx14"] >= 15),
        ),
        Setup(
            "bollinger_squeeze_breakout_long",
            "LONG",
            "volatility",
            "Bollinger width is compressed, then price breaks the upper band with volume confirmation.",
            lambda d: (d["bb_width_rank120"].shift(1) <= 0.25) & (d["close"] > d["bb_upper"]) & (d["volume_ratio20"] >= 1.0),
        ),
        Setup(
            "rsi_reversal_long",
            "LONG",
            "reversal",
            "RSI recovers from oversold while price remains above EMA200.",
            lambda d: _cross_up(d["rsi14"], pd.Series(35, index=d.index)) & (d["rsi14"].shift(1) <= 35) & (d["close"] > d["ema200"]),
        ),
        Setup(
            "adx_trend_continuation_long",
            "LONG",
            "trend",
            "Positive DMI structure with ADX and price above EMA20/EMA50.",
            lambda d: (d["plus_di"] > d["minus_di"]) & (d["adx14"] >= 22) & (d["close"] > d["ema20"]) & (d["ema20"] > d["ema50"]),
        ),
        Setup(
            "breakdown_short",
            "SHORT",
            "breakdown",
            "20-day breakdown with relative volume, bearish EMA structure and ADX confirmation.",
            lambda d: (d["close"] < d["prior_low20"]) & (d["volume_ratio20"] >= 1.2) & (d["ema20"] < d["ema50"]) & (d["adx14"] >= 18),
        ),
        Setup(
            "pullback_fail_short",
            "SHORT",
            "pullback",
            "Bearish EMA structure, RSI bounces into 45-62, then close loses EMA20.",
            lambda d: (d["close"] < d["ema50"]) & (d["ema20"] < d["ema50"]) & d["rsi14"].between(45, 62) & _cross_down(d["close"], d["ema20"]),
        ),
    ]


def _trade_returns(df: pd.DataFrame, signal: pd.Series, direction: str) -> pd.DataFrame:
    rows = []
    signal = signal.fillna(False)
    signal_positions = np.flatnonzero(signal.to_numpy())
    for idx in signal_positions:
        entry_idx = idx + 1
        exit_idx = entry_idx + HOLD_DAYS
        if exit_idx >= len(df):
            continue
        entry = float(df["close"].iloc[entry_idx])
        exit_price = float(df["close"].iloc[exit_idx])
        if entry <= 0 or exit_price <= 0:
            continue
        raw_return = (exit_price / entry - 1) * 100
        if direction == "SHORT":
            raw_return *= -1
        net_return = raw_return - ROUND_TRIP_COST_BPS / 100
        rows.append(
            {
                "date": df.index[entry_idx].date().isoformat(),
                "entry": entry,
                "exit": exit_price,
                "raw_return_pct": round(raw_return, 4),
                "net_return_pct": round(net_return, 4),
                "vol20": _safe_float(df["vol20"].iloc[entry_idx]),
                "adx14": _safe_float(df["adx14"].iloc[entry_idx]),
            }
        )
    return pd.DataFrame(rows)


def _regime(row: pd.Series) -> str:
    if row.get("adx14", 0) is not None and row.get("adx14", 0) >= 22:
        return "trend"
    if row.get("vol20", 0) is not None and row.get("vol20", 0) >= 45:
        return "high_vol"
    return "normal"


def _metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {
            "signals": 0,
            "status": "NO_SAMPLE",
            "avg_return_pct": None,
            "median_return_pct": None,
            "win_rate_pct": None,
            "profit_factor": None,
            "max_drawdown_pct": None,
            "t_stat": None,
            "robustness_score": -999,
        }
    returns = trades["net_return_pct"].astype(float)
    pf = _profit_factor(returns)
    win_rate = float((returns > 0).mean() * 100)
    avg = float(returns.mean())
    t_stat = _t_stat(returns)
    drawdown = _max_drawdown(returns)
    sample_penalty = 0 if len(returns) >= MIN_SIGNALS else (MIN_SIGNALS - len(returns)) * 0.08
    robustness = avg * 2 + (win_rate - 50) * 0.03 + (min(pf or 0, 4) - 1) * 0.4 + (t_stat or 0) * 0.15 + drawdown * 0.03 - sample_penalty
    return {
        "signals": int(len(returns)),
        "status": "PASS" if len(returns) >= MIN_SIGNALS and avg > 0 and win_rate >= 52 and (pf or 0) > 1.1 else "RESEARCH",
        "avg_return_pct": round(avg, 4),
        "median_return_pct": round(float(returns.median()), 4),
        "win_rate_pct": round(win_rate, 2),
        "profit_factor": round(pf, 4) if pf is not None else None,
        "max_drawdown_pct": round(drawdown, 4),
        "t_stat": round(t_stat, 4) if t_stat is not None else None,
        "robustness_score": round(robustness, 4),
    }


def _audit_symbol(symbol: str, setup: Setup) -> tuple[pd.DataFrame, dict]:
    history = market_data_service.get_bars(symbol, period=PERIOD, interval=INTERVAL)
    provider = history.attrs.get("provider", market_data_service.default_service.provider.name)
    if history.empty:
        return pd.DataFrame(), {"symbol": symbol, "provider": provider, "rows": 0, "status": "NO_DATA"}
    df = _prep(history)
    signal = setup.signal_fn(df)
    trades = _trade_returns(df, signal, setup.direction)
    if not trades.empty:
        trades.insert(0, "symbol", symbol)
        trades["regime"] = trades.apply(_regime, axis=1)
    return trades, {"symbol": symbol, "provider": provider, "rows": int(len(history)), "status": "OK"}


def build_report() -> dict:
    symbols = _symbols() or DEFAULT_SYMBOLS
    setups = _setups()
    setup_rows = []
    symbol_rows = []
    all_trades_by_setup: dict[str, pd.DataFrame] = {}

    for setup in setups:
        setup_trades = []
        for symbol in symbols:
            trades, symbol_meta = _audit_symbol(symbol, setup)
            symbol_rows.append({"setup": setup.name, **symbol_meta})
            if not trades.empty:
                setup_trades.append(trades)
        combined = pd.concat(setup_trades, ignore_index=True) if setup_trades else pd.DataFrame()
        all_trades_by_setup[setup.name] = combined
        overall = _metrics(combined)
        by_regime = {}
        if not combined.empty:
            by_regime = {regime: _metrics(group) for regime, group in combined.groupby("regime")}
        setup_rows.append(
            {
                "setup": setup.name,
                "direction": setup.direction,
                "category": setup.category,
                "description": setup.description,
                **overall,
                "by_regime": by_regime,
            }
        )

    ranked = sorted(setup_rows, key=lambda row: row["robustness_score"], reverse=True)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": PERIOD,
        "interval": INTERVAL,
        "hold_days": HOLD_DAYS,
        "round_trip_cost_bps": ROUND_TRIP_COST_BPS,
        "symbols": symbols,
        "provider_counts": {
            str(provider): int(count)
            for provider, count in (pd.DataFrame(symbol_rows)["provider"].value_counts().items() if symbol_rows else [])
        },
        "setups_ranked": ranked,
        "symbol_coverage": symbol_rows,
    }


def main() -> None:
    report = build_report()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("INDICATOR SETUP AUDIT")
    print("=" * 72)
    print(f"Report: {OUT_PATH}")
    print(pd.DataFrame(report["setups_ranked"])[[
        "setup",
        "direction",
        "signals",
        "status",
        "avg_return_pct",
        "win_rate_pct",
        "profit_factor",
        "max_drawdown_pct",
        "t_stat",
        "robustness_score",
    ]].to_string(index=False))


if __name__ == "__main__":
    main()
