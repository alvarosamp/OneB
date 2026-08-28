"""Validate the MTF Liquidity Structure rules with M1 bars exported from MetaTrader 5.

Usage:
  python scripts/validate_mtf_liquidity.py --csv C:\\export\\XAUUSD_M1.csv --symbol XAUUSD

The CSV needs time, open, high, low and close columns. MT5's usual tab-separated
export is accepted too. Results use completed candles only and are not investment advice.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def load_bars(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, sep=None, engine="python")
    raw.columns = [str(c).strip().lower().replace("<", "").replace(">", "") for c in raw.columns]
    if "date" in raw and "time" in raw:
        raw["time"] = raw["date"].astype(str) + " " + raw["time"].astype(str)
    required = {"time", "open", "high", "low", "close"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"CSV needs columns {sorted(required)}; missing {sorted(missing)}")
    bars = raw[["time", "open", "high", "low", "close"]].copy()
    bars["time"] = pd.to_datetime(bars["time"], dayfirst=False, errors="raise")
    for column in ["open", "high", "low", "close"]:
        bars[column] = pd.to_numeric(bars[column], errors="raise")
    return bars.drop_duplicates("time").sort_values("time").set_index("time")


def resample_ohlc(bars: pd.DataFrame, rule: str) -> pd.DataFrame:
    return bars.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    ).dropna()


def confirmed_swings(frame: pd.DataFrame, strength: int = 3) -> tuple[pd.Series, pd.Series]:
    highs, lows = frame.high, frame.low
    sh = pd.Series(True, index=frame.index)
    sl = pd.Series(True, index=frame.index)
    for n in range(1, strength + 1):
        sh &= (highs > highs.shift(n)) & (highs > highs.shift(-n))
        sl &= (lows < lows.shift(n)) & (lows < lows.shift(-n))
    # Make a swing available only once its right-side bars have closed.
    return highs.where(sh).shift(strength), lows.where(sl).shift(strength)


def run_strategy(m1: pd.DataFrame, strength: int = 3) -> pd.DataFrame:
    h4, h1, m15, m5 = (resample_ohlc(m1, rule) for rule in ("4h", "1h", "15min", "5min"))
    h4_sh, h4_sl = confirmed_swings(h4, strength)
    h4_ema = h4.close.ewm(span=50, adjust=False, min_periods=50).mean()
    h4_dir = pd.Series(np.select([h4.close > h4_sh.ffill(), h4.close < h4_sl.ffill()], [1, -1], default=0), index=h4.index)
    h4_dir = h4_dir.mask(h4_dir.eq(0) & (h4.close > h4_ema) & (h4_ema > h4_ema.shift()), 1)
    h4_dir = h4_dir.mask(h4_dir.eq(0) & (h4.close < h4_ema) & (h4_ema < h4_ema.shift()), -1)

    h1_sh, h1_sl = confirmed_swings(h1, strength)
    h1_bull = (h1.close > h1_sh.ffill()).astype(int).where(lambda x: x.eq(1)).ffill(limit=12).notna()
    h1_bear = (h1.close < h1_sl.ffill()).astype(int).where(lambda x: x.eq(1)).ffill(limit=12).notna()
    m15_prior_low = m15.low.shift(1).rolling(20).min()
    m15_prior_high = m15.high.shift(1).rolling(20).max()
    m15_bull = (m15.low < m15_prior_low) & (m15.close > m15_prior_low)
    m15_bear = (m15.high > m15_prior_high) & (m15.close < m15_prior_high)
    m5_bull = m5.close > m5.high.shift(1).rolling(5).max()
    m5_bear = m5.close < m5.low.shift(1).rolling(5).min()
    m1_bull = m1.close > m1.high.shift(1).rolling(5).max()
    m1_bear = m1.close < m1.low.shift(1).rolling(5).min()

    def align(series: pd.Series) -> pd.Series:
        return series.reindex(m1.index, method="ffill").fillna(False)

    # A higher-timeframe OHLC row is knowable only at the opening of its next
    # bar. Shifting prevents a bar from being used before it has closed.
    direction = h4_dir.shift(1).reindex(m1.index, method="ffill").fillna(0)
    long_signal = (direction.eq(1) & align(h1_bull.shift(1)) & align(m15_bull.shift(1)) & align(m5_bull.shift(1)) & m1_bull)
    short_signal = (direction.eq(-1) & align(h1_bear.shift(1)) & align(m15_bear.shift(1)) & align(m5_bear.shift(1)) & m1_bear)
    signals = pd.DataFrame({"side": np.select([long_signal, short_signal], ["long", "short"], default=""), "entry": m1.close})
    return signals[signals.side.ne("")]


def evaluate(m1: pd.DataFrame, signals: pd.DataFrame, horizon: int = 60) -> dict[str, object]:
    moves: list[float] = []
    for timestamp, signal in signals.iterrows():
        future = m1.loc[timestamp:].iloc[1 : horizon + 1]
        if future.empty:
            continue
        move = (future.close.iloc[-1] / signal.entry - 1) * (1 if signal.side == "long" else -1)
        moves.append(float(move))
    values = pd.Series(moves, dtype=float)
    return {"signals_evaluable": int(len(values)), "win_rate_60m": round(float((values > 0).mean()), 4) if len(values) else None,
            "mean_return_60m_pct": round(float(values.mean() * 100), 4) if len(values) else None,
            "median_return_60m_pct": round(float(values.median() * 100), 4) if len(values) else None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--symbol", required=True, help="broker symbol, e.g. XAUUSD or NAS100")
    parser.add_argument("--output", type=Path, default=Path("output/mtf_validation"))
    args = parser.parse_args()
    bars = load_bars(args.csv)
    signals = run_strategy(bars)
    args.output.mkdir(parents=True, exist_ok=True)
    signals.to_csv(args.output / f"{args.symbol}_signals.csv")
    report = {"symbol": args.symbol, "bars_m1": len(bars), "from": str(bars.index.min()), "to": str(bars.index.max()),
              "signals": int(len(signals)), **evaluate(bars, signals)}
    (args.output / f"{args.symbol}_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
