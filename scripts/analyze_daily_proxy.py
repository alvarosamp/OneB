"""Proxy validation of the MTF Liquidity Structure premise using ONLY the daily
bars already cached in the user's repo (no real M1 data available to me).

This does NOT reproduce the real 5-timeframe (H4/H1/M15/M5/M1) cascade — that
needs true intraday data from MT5. What it does is take the same two building
blocks the real strategy is built from (confirmed swing-structure direction,
and a liquidity-sweep-and-reclaim event) and test them, stacked together, on
daily bars for Gold (GC=F) and Nasdaq (NQ=F futures, QQQ ETF as a longer
cross-check). This tells us whether the *premise* (trade in the direction of
confirmed structure, entering after a liquidity sweep) has any historical
merit at all on these two instruments -- a sanity check one timeframe removed
from the real system, not a replacement for the MT5 M1 validation.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

from scripts.validate_mtf_liquidity import confirmed_swings


def load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_localize(None)
    df = df.set_index("timestamp").sort_index()
    return df[["open", "high", "low", "close"]]


def structure_direction(df: pd.DataFrame, strength: int = 3) -> pd.Series:
    sh, sl = confirmed_swings(df, strength)
    sh_ffill, sl_ffill = sh.ffill(), sl.ffill()
    ema = df.close.ewm(span=50, adjust=False, min_periods=50).mean()
    direction = pd.Series(
        np.select([df.close > sh_ffill, df.close < sl_ffill], [1, -1], default=0),
        index=df.index,
    )
    direction = direction.mask(direction.eq(0) & (df.close > ema) & (ema > ema.shift()), 1)
    direction = direction.mask(direction.eq(0) & (df.close < ema) & (ema < ema.shift()), -1)
    # Never trade on the same bar structure was confirmed -- act next bar only.
    return direction.shift(1)


def liquidity_sweep(df: pd.DataFrame, lookback: int = 20) -> pd.Series:
    prior_low = df.low.shift(1).rolling(lookback).min()
    prior_high = df.high.shift(1).rolling(lookback).max()
    bull = (df.low < prior_low) & (df.close > prior_low)
    bear = (df.high > prior_high) & (df.close < prior_high)
    return pd.Series(np.select([bull, bear], [1, -1], default=0), index=df.index)


def forward_return(df: pd.DataFrame, horizon: int) -> pd.Series:
    return df.close.shift(-horizon) / df.close - 1


def stats(sample: pd.Series) -> dict:
    n = int(sample.count())
    if n == 0:
        return {"n": 0, "hit_rate": None, "mean_pct": None, "median_pct": None, "t_stat": None}
    mean, std = sample.mean(), sample.std(ddof=1)
    t = float(mean / (std / math.sqrt(n))) if std and n > 1 else None
    return {
        "n": n,
        "hit_rate": round(float((sample > 0).mean()), 4),
        "mean_pct": round(float(mean * 100), 4),
        "median_pct": round(float(sample.median() * 100), 4),
        "t_stat": round(t, 3) if t is not None else None,
    }


def evaluate(symbol: str, df: pd.DataFrame, horizons=(5, 10, 20)) -> dict:
    direction = structure_direction(df)
    sweep = liquidity_sweep(df).shift(1)  # sweep known at the start of the next bar
    aligned_sweep = np.sign(sweep) == direction
    base_mask = direction != 0
    stacked_mask = base_mask & (sweep != 0) & aligned_sweep

    out = {"symbol": symbol, "bars": len(df), "from": str(df.index.min().date()), "to": str(df.index.max().date())}
    for h in horizons:
        fwd = forward_return(df, h) * np.sign(direction.replace(0, np.nan))
        out[f"structure_only_{h}d"] = stats(fwd[base_mask].dropna())
        out[f"structure_plus_sweep_{h}d"] = stats(fwd[stacked_mask].dropna())
    out["sweep_events"] = int((sweep != 0).sum())
    out["structure_plus_sweep_signals"] = int(stacked_mask.sum())
    return out


def main():
    root = Path("data/raw/prices/yfinance")
    targets = {
        "GC=F (Gold futures, 1y)": root / "1d" / "GC=F.csv",
        "NQ=F (Nasdaq futures, 2y)": root / "1d" / "2y" / "NQ=F.csv",
        "QQQ (Nasdaq-100 ETF, 2y)": root / "1d" / "QQQ.csv",
    }
    results = {}
    for label, path in targets.items():
        df = load(path)
        results[label] = evaluate(label, df)
    Path("output/mtf_validation").mkdir(parents=True, exist_ok=True)
    Path("output/mtf_validation/daily_proxy_validation.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
