"""Research-backed, cross-sectional technical edge ranking.

This module deliberately produces an *observation* score rather than a trade
instruction.  Its feature directions come from the 2026-08-13 walk-forward
research audit and must be revalidated whenever the universe or horizon
changes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app import indicators


HORIZON_DAYS = 5
# A positive sign means that a higher cross-sectional rank was beneficial in
# the audited sample.  The negative short-horizon momentum signs are
# intentional: the sample showed mean reversion, not a breakout edge.
FEATURE_DIRECTIONS = {
    "mom_accel_5v20": -1,
    "adx14": 1,
    "ret_5d": -1,
    "rel_ret_5d_vs_qqq": -1,
    "annualized_volatility": 1,
    "macd_hist_slope_3d": -1,
    "high20_breakout_pct": -1,
    "ema20_50_gap_pct": 1,
}


def feature_frame(history: pd.DataFrame, benchmark: pd.DataFrame) -> pd.DataFrame:
    """Return the audited feature set for one symbol, aligned to its candles."""
    required = {"high", "low", "close"}
    if history.empty or not required.issubset(history.columns):
        return pd.DataFrame(index=history.index)
    close = history["close"]
    adx = indicators.adx(history["high"], history["low"], close)
    macd = indicators.macd(close)
    ema20 = indicators.ema(close, 20)
    ema50 = indicators.ema(close, 50)
    high20 = history["high"].rolling(20, min_periods=20).max().shift(1)

    benchmark_close = benchmark.get("close", pd.Series(dtype=float)).reindex(history.index, method="ffill")
    out = pd.DataFrame(index=history.index)
    out["ret_5d"] = close.pct_change(5) * 100
    out["mom_accel_5v20"] = out["ret_5d"] - close.pct_change(20) * 25
    out["adx14"] = adx["adx"]
    out["annualized_volatility"] = indicators.annualized_volatility(close)
    out["macd_hist_slope_3d"] = macd["histogram"] - macd["histogram"].shift(3)
    out["high20_breakout_pct"] = (close / high20 - 1) * 100
    out["ema20_50_gap_pct"] = (ema20 / ema50 - 1) * 100
    out["rel_ret_5d_vs_qqq"] = out["ret_5d"] - benchmark_close.pct_change(5) * 100
    return out.replace([np.inf, -np.inf], np.nan)


def rank_latest(histories: dict[str, pd.DataFrame], benchmark: pd.DataFrame) -> list[dict]:
    """Rank symbols by the latest common, research-defined feature score.

    Insufficient data is returned as ``SEM_LEITURA`` instead of being silently
    ranked.  This prevents a young listing or stale feed from looking strong.
    """
    rows = []
    for symbol, history in histories.items():
        features = feature_frame(history, benchmark)
        if features.empty or features.iloc[-1].isna().any():
            rows.append({"symbol": symbol.upper(), "status": "SEM_LEITURA"})
            continue
        latest = features.iloc[-1]
        row = {"symbol": symbol.upper(), "status": "OK"}
        row.update({name: float(latest[name]) for name in FEATURE_DIRECTIONS})
        rows.append(row)

    valid = pd.DataFrame([row for row in rows if row["status"] == "OK"])
    if not valid.empty:
        contributions = []
        for feature, direction in FEATURE_DIRECTIONS.items():
            col = f"{feature}_contribution"
            valid[col] = direction * (valid[feature].rank(pct=True) - 0.5)
            contributions.append(col)
        valid["edge_score"] = valid[contributions].mean(axis=1) * 100
        valid["rank"] = valid["edge_score"].rank(method="min", ascending=False).astype(int)
        valid["universe_size"] = len(valid)
        valid["label"] = np.select(
            [valid["edge_score"] >= 15, valid["edge_score"] <= -15],
            ["OBSERVAR", "FRACO"],
            default="NEUTRO",
        )
        row_positions = {row["symbol"]: position for position, row in enumerate(rows)}
        for row in valid.to_dict(orient="records"):
            row["edge_score"] = round(float(row["edge_score"]), 2)
            rows[row_positions[row["symbol"]]] = row

    return sorted(rows, key=lambda row: (row["status"] != "OK", -row.get("edge_score", -999)))
