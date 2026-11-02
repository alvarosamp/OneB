"""Classificação de regime de tendência e de volatilidade, sem olhar o futuro."""
from __future__ import annotations

import numpy as np
import pandas as pd

TREND_LABELS = {"up": "alta", "down": "baixa", "sideways": "lateral"}
VOL_LABELS = {"high": "alta", "normal": "normal", "low": "baixa"}


def trend_regime(close: pd.Series, fast: int = 50, slow: int = 200) -> pd.Series:
    """'up': preço e média rápida acima da lenta; 'down': ambos abaixo; senão 'sideways'.

    Antes de haver `slow` barras o valor é NaN (sem regime definido).
    """
    sma_fast = close.rolling(fast).mean()
    sma_slow = close.rolling(slow).mean()
    up = (close > sma_slow) & (sma_fast > sma_slow)
    down = (close < sma_slow) & (sma_fast < sma_slow)
    out = pd.Series(np.where(up, "up", np.where(down, "down", "sideways")), index=close.index, dtype=object)
    out[sma_slow.isna()] = np.nan
    return out


def volatility_regime(close: pd.Series, window: int = 20, lookback: int = 252) -> pd.Series:
    """Volatilidade realizada anualizada comparada aos percentis 20/80 do próprio passado."""
    vol = np.log(close).diff().rolling(window).std() * np.sqrt(252)
    hist = vol.rolling(lookback, min_periods=60)
    high = vol > hist.quantile(0.8)
    low = vol < hist.quantile(0.2)
    out = pd.Series(np.where(high, "high", np.where(low, "low", "normal")), index=close.index, dtype=object)
    out[hist.quantile(0.8).isna() | vol.isna()] = np.nan
    return out


def _run_length(regime: pd.Series) -> int:
    valid = regime.dropna()
    if valid.empty:
        return 0
    changed = valid != valid.iloc[-1]
    if not changed.any():
        return len(valid)
    return len(valid) - 1 - int(np.flatnonzero(changed.to_numpy())[-1])


def regime_summary(close: pd.Series) -> dict:
    """Regime atual e há quantas barras ele dura."""
    close = close.dropna()
    trend = trend_regime(close)
    vol = volatility_regime(close)
    t = trend.dropna()
    v = vol.dropna()
    return {
        "trend": t.iloc[-1] if len(t) else None,
        "trend_label": TREND_LABELS.get(t.iloc[-1]) if len(t) else None,
        "trend_bars": _run_length(trend),
        "volatility": v.iloc[-1] if len(v) else None,
        "volatility_label": VOL_LABELS.get(v.iloc[-1]) if len(v) else None,
        "volatility_bars": _run_length(vol),
    }


def forward_return_by_regime(close: pd.Series, regime: pd.Series, horizon: int = 5) -> pd.DataFrame:
    """Retorno médio futuro (%) condicionado ao regime vigente na data da observação."""
    fwd = (close.shift(-horizon) / close - 1) * 100
    df = pd.DataFrame({"regime": regime, "fwd": fwd}).dropna()
    if df.empty:
        return pd.DataFrame(columns=["regime", "n", "mean_pct", "median_pct", "hit_rate"])
    g = df.groupby("regime")["fwd"]
    out = pd.DataFrame(
        {
            "n": g.size(),
            "mean_pct": g.mean().round(3),
            "median_pct": g.median().round(3),
            "hit_rate": g.apply(lambda s: round(float((s > 0).mean()), 3)),
        }
    )
    return out.reset_index()
