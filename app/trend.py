"""Tendência de 1, 3 e 12 meses (time-series momentum), conforme o pré-registro tsmom_v1.

Duas utilidades:
- backtest(): o teste pré-registrado (portfólio mensal líquido de custos).
- reading(): a leitura atual de um instrumento para a tela "Leitura de tendência"
  (direção por horizonte, volatilidade e o preço que viraria cada horizonte).

Nada aqui gera ordem. A decisão de mostrar a direção como evidência depende do
veredito do teste (ver evaluate()).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DAILY_DIR = Path(r"D:\OneB\market-data\dukascopy-daily\normalized")
ANNUAL_DAYS = 261
LOOKBACKS = (21, 63, 252)
HORIZON_LABEL = {21: "1 mês", 63: "3 meses", 252: "12 meses"}


@dataclass(frozen=True)
class TrendParams:
    lookbacks: tuple[int, ...] = LOOKBACKS
    target_vol: float = 0.10
    max_weight: float = 5.0
    vol_com: int = 60
    min_history: int = 252 + 60
    financing_annual: float = 0.02
    slippage: float = 0.0002


def load_daily(instrument: str, directory: Path = DAILY_DIR) -> pd.DataFrame:
    frame = pd.read_csv(directory / f"{instrument}_D1.csv.gz")
    frame.index = pd.to_datetime(frame["timestamp"], unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
    return frame[["close", "spread"]].astype(float)


def ewma_vol(returns: pd.Series, com: int = 60) -> pd.Series:
    """Volatilidade anualizada pela EWMA dos retornos ao quadrado (só passado até o dia)."""
    return np.sqrt((returns**2).ewm(com=com, min_periods=com).mean() * ANNUAL_DAYS)


def month_end_days(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    s = pd.Series(index, index=index)
    return pd.DatetimeIndex(s.groupby([index.year, index.month]).max().values)


def instrument_daily(frame: pd.DataFrame, params: TrendParams, *, long_only: bool = False,
                     lookbacks: tuple[int, ...] | None = None) -> pd.DataFrame:
    """Retorno diário líquido de um instrumento com rebalanceamento no fim do mês.

    O peso decidido no fechamento do último dia útil do mês vale a partir do dia
    seguinte (shift), então nenhum retorno usa informação do próprio dia.
    """
    lookbacks = lookbacks or params.lookbacks
    close = frame["close"]
    ret = close.pct_change()
    vol = ewma_vol(ret, params.vol_com)
    half_spread = (frame["spread"] / close / 2).rolling(20, min_periods=5).median()
    target = pd.Series(np.nan, index=frame.index)
    for day in month_end_days(frame.index):
        pos = frame.index.get_loc(day)
        if pos < params.min_history or not np.isfinite(vol.iloc[pos]) or vol.iloc[pos] <= 0:
            continue
        if long_only:
            signal = 1.0
        else:
            signs = [np.sign(close.iloc[pos] / close.iloc[pos - L] - 1) for L in lookbacks]
            signal = float(np.mean(signs))
        target.iloc[pos] = float(np.clip(signal * params.target_vol / vol.iloc[pos], -params.max_weight, params.max_weight))
    weight = target.ffill()
    held = weight.shift(1)  # vale a partir do dia seguinte ao rebalanceamento
    # Troca de posição no fechamento do dia de rebalanceamento; o custo entra nesse dia.
    turnover = (weight - weight.shift(1).fillna(0)).abs().where(target.notna(), 0.0)
    cost = turnover * (half_spread.fillna(half_spread.median()) + params.slippage)
    financing = held.abs() * params.financing_annual / ANNUAL_DAYS
    gross = held * ret
    net = gross.fillna(0) - financing.fillna(0) - cost.fillna(0)
    # A partir do primeiro rebalanceamento (inclui o custo de entrada desse dia).
    return pd.DataFrame({"weight": held, "gross": gross.fillna(0), "net": net})[weight.notna()]


def monthly(daily: pd.Series) -> pd.Series:
    return (1 + daily).groupby([daily.index.year, daily.index.month]).prod() - 1


def portfolio_monthly(frames: dict[str, pd.DataFrame], params: TrendParams, **kwargs) -> tuple[pd.Series, pd.DataFrame]:
    per = {}
    for name, frame in frames.items():
        d = instrument_daily(frame, params, **kwargs)
        if len(d):
            m = monthly(d["net"])
            m.index = pd.PeriodIndex([pd.Period(year=y, month=mo, freq="M") for y, mo in m.index])
            per[name] = m
    table = pd.DataFrame(per).sort_index()
    return table.mean(axis=1, skipna=True), table


def block_bootstrap_mean(values: np.ndarray, block: int = 12, resamples: int = 10_000, seed: int = 7) -> np.ndarray:
    """Médias de reamostragens em blocos circulares (preserva autocorrelação mensal)."""
    n = len(values)
    rng = np.random.default_rng(seed)
    blocks = int(np.ceil(n / block))
    starts = rng.integers(0, n, size=(resamples, blocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(resamples, -1)[:, :n] % n
    return values[idx].mean(axis=1)


def ci(values: np.ndarray, alpha: float = 0.05, **kw) -> tuple[float, float]:
    means = block_bootstrap_mean(values, **kw)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def alpha_vs(strategy: pd.Series, benchmark: pd.Series, resamples: int = 10_000, seed: int = 7) -> dict:
    df = pd.concat([strategy, benchmark], axis=1, keys=["s", "b"]).dropna()
    x, y = df["b"].to_numpy(), df["s"].to_numpy()

    def fit(xx, yy):
        beta = np.cov(xx, yy, ddof=1)[0, 1] / np.var(xx, ddof=1)
        return yy.mean() - beta * xx.mean(), beta

    a, b = fit(x, y)
    n, block = len(df), 12
    rng = np.random.default_rng(seed)
    blocks = int(np.ceil(n / block))
    alphas = []
    for _ in range(resamples):
        idx = ((rng.integers(0, n, size=blocks)[:, None] + np.arange(block)[None, :]).ravel()[:n]) % n
        alphas.append(fit(x[idx], y[idx])[0])
    return {"alpha_monthly": round(float(a), 5), "beta": round(float(b), 3),
            "alpha_ci95": [round(float(np.quantile(alphas, 0.025)), 5), round(float(np.quantile(alphas, 0.975)), 5)],
            "correlation": round(float(np.corrcoef(x, y)[0, 1]), 3)}


def summary(series: pd.Series) -> dict:
    v = series.dropna().to_numpy()
    if len(v) < 2:
        return {"months": len(v)}
    curve = np.cumprod(1 + v)
    dd = float((curve / np.maximum.accumulate(curve) - 1).min())
    lo, hi = ci(v)
    return {"months": int(len(v)), "mean_monthly": round(float(v.mean()), 5), "ci95": [round(lo, 5), round(hi, 5)],
            "sharpe_annual": round(float(v.mean() / v.std(ddof=1) * np.sqrt(12)), 3) if v.std(ddof=1) > 0 else None,
            "annual_return": round(float(curve[-1] ** (12 / len(v)) - 1), 4), "max_drawdown": round(dd, 4)}


def verdict(primary_ci: tuple[float, float], recent_mean: float | None) -> dict:
    lo, hi = primary_ci
    if hi < 0:
        return {"status": "FAILED", "reason": "IC 95% inteiro abaixo de zero."}
    if lo <= 0:
        return {"status": "NOT_SIGNIFICANT", "reason": "IC 95% contém zero: sem evidência de tendência após custos."}
    if recent_mean is None or recent_mean <= 0:
        return {"status": "DEGRADED", "reason": "Positivo no período todo, mas não no período recente."}
    return {"status": "PASSED", "reason": "IC 95% acima de zero e período recente positivo."}


def reading(frame: pd.DataFrame, params: TrendParams = TrendParams()) -> dict:
    """Leitura atual: direção por horizonte e o preço que viraria cada uma.

    O "preço de virada" de um horizonte L é o fechamento de L pregões atrás:
    acima dele o retorno de L dias é positivo, abaixo é negativo.
    """
    close = frame["close"].dropna()
    ret = close.pct_change()
    vol = ewma_vol(ret, params.vol_com)
    last = float(close.iloc[-1])
    horizons = []
    for L in params.lookbacks:
        if len(close) <= L:
            continue
        ref = float(close.iloc[-1 - L])
        change = last / ref - 1
        horizons.append({"days": L, "label": HORIZON_LABEL.get(L, f"{L} dias"), "direction": "alta" if change > 0 else "baixa",
                         "change": round(change, 4), "flip_price": round(ref, 6),
                         "distance_to_flip": round(last / ref - 1, 4)})
    signs = [1 if h["direction"] == "alta" else -1 for h in horizons]
    agreement = "todos em alta" if signs and all(s > 0 for s in signs) else "todos em baixa" if signs and all(s < 0 for s in signs) else "misto"
    v = float(vol.iloc[-1]) if np.isfinite(vol.iloc[-1]) else None
    pct = float((vol.dropna() <= vol.iloc[-1]).mean()) if v is not None else None
    return {"as_of": str(close.index[-1].date()), "last": last, "horizons": horizons, "combined": round(float(np.mean(signs)), 3) if signs else None,
            "agreement": agreement, "volatility_annual": round(v, 4) if v else None,
            "volatility_percentile": round(pct, 3) if pct is not None else None}
