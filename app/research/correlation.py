"""Correlações entre ativos, com cuidado estatístico.

Testar muitos pares gera "achados" por puro acaso; por isso cada correlação vem com
p-valor, p-valor ajustado (Benjamini-Hochberg) e o tamanho da amostra. Sem scipy: o
p-valor usa a transformação z de Fisher, boa aproximação para n >= ~30.
"""
from __future__ import annotations

import math
from itertools import combinations

import numpy as np
import pandas as pd


def log_returns(prices: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    return np.log(prices).diff().replace([np.inf, -np.inf], np.nan)


def correlation_pvalue(r: float, n: int) -> float | None:
    """p-valor bilateral de H0: correlação = 0 (Fisher z)."""
    if n < 4 or r is None or math.isnan(r):
        return None
    r = max(min(r, 0.999999), -0.999999)
    z = math.atanh(r) * math.sqrt(n - 3)
    return math.erfc(abs(z) / math.sqrt(2))


def benjamini_hochberg(pvalues: list[float | None]) -> list[float | None]:
    """Ajuste de múltiplos testes (controla a taxa de falsas descobertas)."""
    idx = [i for i, p in enumerate(pvalues) if p is not None]
    m = len(idx)
    adjusted: list[float | None] = [None] * len(pvalues)
    if m == 0:
        return adjusted
    order = sorted(idx, key=lambda i: pvalues[i])
    running = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, pvalues[i] * m / rank)
        adjusted[i] = running
    return adjusted


def pair_correlations(returns: pd.DataFrame, min_obs: int = 60, alpha: float = 0.05) -> pd.DataFrame:
    """Todas as correlações par a par, ordenadas por |r|.

    Colunas: a, b, r, n, p, p_adj, significant (p_adj < alpha).
    """
    rows = []
    for a, b in combinations(returns.columns, 2):
        pair = returns[[a, b]].dropna()
        n = len(pair)
        if n < min_obs:
            continue
        r = float(pair[a].corr(pair[b]))
        if math.isnan(r):
            continue
        rows.append({"a": a, "b": b, "r": round(r, 4), "n": n, "p": correlation_pvalue(r, n)})

    cols = ["a", "b", "r", "n", "p", "p_adj", "significant"]
    if not rows:
        return pd.DataFrame(columns=cols)

    df = pd.DataFrame(rows)
    df["p_adj"] = benjamini_hochberg(df["p"].tolist())
    df["significant"] = df["p_adj"] < alpha
    df["p"] = df["p"].round(6)
    df["p_adj"] = df["p_adj"].round(6)
    return df.reindex(df["r"].abs().sort_values(ascending=False).index).reset_index(drop=True)[cols]


def rolling_correlation(a: pd.Series, b: pd.Series, window: int = 60) -> pd.Series:
    return a.rolling(window, min_periods=window).corr(b)


def correlation_drift(returns: pd.DataFrame, recent: int = 60, min_obs: int = 120) -> pd.DataFrame:
    """Compara a correlação recente com a de todo o período — detecta relações que mudaram.

    Colunas: a, b, r_full, r_recent, delta (recente - total), ordenadas por |delta|.
    """
    rows = []
    for a, b in combinations(returns.columns, 2):
        pair = returns[[a, b]].dropna()
        if len(pair) < min_obs:
            continue
        r_full = pair[a].corr(pair[b])
        r_recent = pair.iloc[-recent:][a].corr(pair.iloc[-recent:][b])
        if math.isnan(r_full) or math.isnan(r_recent):
            continue
        rows.append(
            {
                "a": a,
                "b": b,
                "r_full": round(float(r_full), 4),
                "r_recent": round(float(r_recent), 4),
                "delta": round(float(r_recent - r_full), 4),
            }
        )
    cols = ["a", "b", "r_full", "r_recent", "delta"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    return df.reindex(df["delta"].abs().sort_values(ascending=False).index).reset_index(drop=True)[cols]


def lead_lag(a: pd.Series, b: pd.Series, max_lag: int = 5, min_obs: int = 60) -> dict:
    """Correlação de `a` hoje com `b` k dias depois (k > 0: a antecede b; k < 0: b antecede a).

    O melhor lag é o de maior |r| entre os lags testados; o p-valor dele já é corrigido
    pelo número de lags testados (Bonferroni), pois escolher o melhor entre vários infla o acaso.
    """
    results = []
    for k in range(-max_lag, max_lag + 1):
        pair = pd.concat([a, b.shift(-k)], axis=1).dropna()
        n = len(pair)
        if n < min_obs:
            continue
        r = float(pair.iloc[:, 0].corr(pair.iloc[:, 1]))
        if math.isnan(r):
            continue
        results.append({"lag": k, "r": round(r, 4), "n": n})
    if not results:
        return {"lags": [], "best": None}

    best = max(results, key=lambda x: abs(x["r"]))
    p = correlation_pvalue(best["r"], best["n"])
    best = {**best, "p_adj": min(1.0, p * len(results)) if p is not None else None}
    return {"lags": results, "best": best}
