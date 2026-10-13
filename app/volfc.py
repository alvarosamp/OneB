"""Previsão de amplitude diária (volfc_v1): HAR no log da amplitude contra o ATR de 14 dias.

Previsão de RISCO (quanto o preço deve se mover), não de direção. Funções puras;
o teste pré-registrado roda em scripts/run_volfc.py.
"""
from __future__ import annotations

from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

NEW_YORK = ZoneInfo("America/New_York")
MIN_BARS = 150


def trading_days(m5: pd.DataFrame) -> pd.DataFrame:
    """Dias de 17:00 a 17:00 de NY a partir do M5 (índice UTC): high, low, close, bars e range relativo."""
    ny = m5.index.tz_convert(NEW_YORK) if m5.index.tz is not None else m5.index.tz_localize("UTC").tz_convert(NEW_YORK)
    day = (ny + pd.Timedelta(hours=7)).date
    g = m5.groupby(day)
    d = pd.DataFrame({"high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last(), "bars": g["close"].count()})
    d.index = pd.to_datetime(d.index)
    d = d[(d["bars"] >= MIN_BARS) & (d.index.dayofweek < 5)]
    d["range"] = (d["high"] - d["low"]) / d["close"].shift(1)
    return d.dropna(subset=["range"])[lambda x: x["range"] > 0]


def features(log_range: pd.Series) -> pd.DataFrame:
    """Variáveis conhecidas no fechamento do dia t para prever t+1."""
    return pd.DataFrame({
        "d": log_range,
        "w": log_range.rolling(5).mean(),
        "m": log_range.rolling(22).mean(),
        "atr14": np.log(np.exp(log_range).rolling(14).mean()),
        "target": log_range.shift(-1),
    })


def fit_ols(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    A = np.column_stack([np.ones(len(X)), X])
    return np.linalg.lstsq(A, y, rcond=None)[0]


def predict(coef: np.ndarray, X: np.ndarray) -> np.ndarray:
    return coef[0] + X @ coef[1:]


def block_bootstrap_mean_ci(values: np.ndarray, block: int = 20, resamples: int = 2000, seed: int = 7) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = len(values)
    starts = np.arange(max(1, n - block + 1))
    means = np.empty(resamples)
    for i in range(resamples):
        idx = np.concatenate([np.arange(s, s + block) for s in rng.choice(starts, size=int(np.ceil(n / block)))])[:n]
        means[i] = values[idx].mean()
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def forecast_next(daily_range: pd.Series, coef: list[float], q10: float, q90: float) -> dict:
    """Amplitude esperada do próximo dia com a faixa de 80%, a partir das amplitudes diárias até hoje."""
    lr = np.log(daily_range.dropna())
    f = features(lr).iloc[-1]
    x = np.array([f["d"], f["w"], f["m"]])
    mid = float(predict(np.asarray(coef), x[None, :])[0])
    return {"expected": float(np.exp(mid)), "low80": float(np.exp(mid + q10)), "high80": float(np.exp(mid + q90))}
