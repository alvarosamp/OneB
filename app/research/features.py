"""Features causais (só usam dados até o fechamento de t) e alvo executável (abertura t+1 -> t+1+h)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app import indicators as ind
from app.research.strategies import atr

HORIZON = 5


def symbol_features(d: pd.DataFrame) -> pd.DataFrame:
    c, h, l, v = d["close"], d["high"], d["low"], d["volume"]
    r1 = c.pct_change()
    f = pd.DataFrame(index=d.index)
    for n in (1, 5, 10, 20, 60, 120):
        f[f"ret_{n}"] = c.pct_change(n)
    f["mom_12_1"] = c.shift(21) / c.shift(252) - 1
    f["vol_20"] = r1.rolling(20).std()
    f["vol_60"] = r1.rolling(60).std()
    f["rsi14"] = ind.rsi(c, 14)
    f["rsi2"] = ind.rsi(c, 2)
    for n in (20, 50, 200):
        f[f"dist_sma{n}"] = c / c.rolling(n).mean() - 1
    f["macd_hist"] = ind.macd(c)["histogram"] / c
    bb = ind.bollinger_bands(c)
    f["bb_pos"] = (c - bb["lower"]) / (bb["upper"] - bb["lower"])
    f["vol_ratio"] = ind.volume_ratio(v, 20).astype(float)
    f["atr_pct"] = atr(d) / c
    lo, hi = l.rolling(252).min(), h.rolling(252).max()
    f["pos_52w"] = (c - lo) / (hi - lo)
    f["gap"] = d["open"] / c.shift(1) - 1
    f["range_pct"] = (h - l) / c
    return f.replace([np.inf, -np.inf], np.nan)


def forward_return(d: pd.DataFrame, horizon: int = HORIZON) -> pd.Series:
    """Compra na abertura de t+1, vende na abertura de t+1+horizon (alinhado ao motor de backtest)."""
    o = d["open"]
    return o.shift(-(1 + horizon)) / o.shift(-1) - 1


def build_panel(data: dict[str, pd.DataFrame], market: pd.DataFrame, horizon: int = HORIZON) -> pd.DataFrame:
    """Painel (data, ativo) com features, retorno futuro e retorno futuro relativo ao grupo."""
    mkt_ret20 = market["close"].pct_change(20)
    frames = []
    for sym, d in data.items():
        f = symbol_features(d)
        f["rel_strength_20"] = f["ret_20"] - mkt_ret20.reindex(f.index)
        f["fwd"] = forward_return(d, horizon)
        f["symbol"] = sym
        frames.append(f)
    panel = pd.concat(frames).reset_index().rename(columns={"timestamp": "date", "index": "date"})
    panel = panel.set_index(["date", "symbol"]).sort_index()
    panel["fwd_rel"] = panel["fwd"] - panel.groupby(level="date")["fwd"].transform("median")
    return panel


def rank_normalize(panel: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Rank percentil por data, centrado em 0 (remove o nível de mercado e outliers)."""
    return panel[cols].groupby(level="date").rank(pct=True) - 0.5
