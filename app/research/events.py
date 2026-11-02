"""Estudo de eventos: o que acontece com o preço depois que um sinal dispara.

O sinal em t usa apenas informação até o fechamento de t; o retorno é medido a partir desse
fechamento (sem look-ahead). Eventos consecutivos são agrupados por `cooldown` para que
janelas de retorno sobrepostas não contem a mesma informação várias vezes.
"""
from __future__ import annotations

import math

import pandas as pd

from app import indicators


def signal_rsi_below(close: pd.Series, level: float = 30.0) -> pd.Series:
    """Dispara na barra em que o RSI cruza para baixo de `level`."""
    r = indicators.rsi(close, 14)
    return (r < level) & (r.shift(1) >= level)


def signal_sma_cross_up(close: pd.Series, fast: int = 50, slow: int = 200) -> pd.Series:
    """Dispara quando a média rápida cruza acima da lenta (golden cross)."""
    f, s = close.rolling(fast).mean(), close.rolling(slow).mean()
    return (f > s) & (f.shift(1) <= s.shift(1))


def apply_cooldown(signal: pd.Series, cooldown: int) -> pd.Series:
    """Mantém um evento e ignora os `cooldown` seguintes."""
    out = pd.Series(False, index=signal.index)
    last = -cooldown - 1
    for i, fired in enumerate(signal.fillna(False).to_numpy()):
        if fired and i - last > cooldown:
            out.iloc[i] = True
            last = i
    return out


def event_study(
    close: pd.Series,
    signal: pd.Series,
    horizons: tuple[int, ...] = (1, 5, 10, 20),
    cooldown: int = 5,
) -> list[dict]:
    """Por horizonte: n de eventos, retorno médio/mediano, taxa de acerto e excesso vs base.

    `excess_pct` é o retorno médio pós-evento menos o retorno médio incondicional da série;
    `t_stat` compara os dois (|t| < 2 ≈ indistinguível do acaso). Poucos eventos (n baixo)
    tornam qualquer conclusão frágil.
    """
    close = close.dropna()
    events = apply_cooldown(signal.reindex(close.index).fillna(False), cooldown)
    rows = []
    for h in horizons:
        fwd = (close.shift(-h) / close - 1) * 100
        after = fwd[events].dropna()
        base = fwd.dropna()
        n = len(after)
        row = {"horizon": h, "n": n, "mean_pct": None, "median_pct": None, "hit_rate": None,
               "baseline_mean_pct": round(float(base.mean()), 3) if len(base) else None,
               "excess_pct": None, "t_stat": None}
        if n >= 1:
            row["mean_pct"] = round(float(after.mean()), 3)
            row["median_pct"] = round(float(after.median()), 3)
            row["hit_rate"] = round(float((after > 0).mean()), 3)
            row["excess_pct"] = round(float(after.mean() - base.mean()), 3)
        if n >= 5 and len(base) > 1:
            se = math.sqrt(after.var(ddof=1) / n + base.var(ddof=1) / len(base))
            if se > 0:
                row["t_stat"] = round(float((after.mean() - base.mean()) / se), 2)
        rows.append(row)
    return rows
