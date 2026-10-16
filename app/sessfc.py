"""Previsão do quanto o preço ainda anda até o fechamento de Nova York (sessfc_v1).

Janela: da barra M5 das 13:30 UTC (10:30 de Brasília, a hora do plano do OneB) até as 16:00 de NY.
Previsão de RISCO (tamanho do movimento), não de direção. Funções puras; o teste pré-registrado
roda em scripts/run_sessfc.py e o app usa as mesmas funções com as barras de 5 min do Yahoo.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

NEW_YORK = ZoneInfo("America/New_York")
ENTRY_UTC = time(13, 30)
CLOSE_NY = time(16, 0)
PRE_START_NY = time(18, 0)  # do dia anterior
MIN_BARS = 24
FEATURES = ["d", "w", "m", "pre", "event"]


def _utc(m5: pd.DataFrame) -> pd.DataFrame:
    d = m5[["open", "high", "low", "close"]].dropna().copy()
    idx = pd.DatetimeIndex(d.index)
    d.index = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    return d[~d.index.duplicated()].sort_index()


def window_bounds(day: date) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    """(início da madrugada, entrada, fechamento) em UTC para o dia útil `day` de Nova York."""
    entry = pd.Timestamp(datetime.combine(day, ENTRY_UTC, tzinfo=timezone.utc))
    close = pd.Timestamp(datetime.combine(day, CLOSE_NY, tzinfo=NEW_YORK)).tz_convert("UTC")
    pre = pd.Timestamp(datetime.combine(day - timedelta(days=1), PRE_START_NY, tzinfo=NEW_YORK)).tz_convert("UTC")
    return pre, entry, close


def windows(m5: pd.DataFrame, complete_only: bool = True) -> pd.DataFrame:
    """Uma linha por dia útil de NY: preço de entrada, amplitude da janela (relativa) e amplitude da madrugada."""
    d = _utc(m5)
    if d.empty:
        return pd.DataFrame(columns=["entry", "range", "pre_range", "bars", "complete"])
    idx = d.index
    hi, lo, op = d["high"].to_numpy(), d["low"].to_numpy(), d["open"].to_numpy()
    last = idx[-1]
    rows = {}
    for day in sorted({t.date() for t in idx.tz_convert(NEW_YORK)}):
        if day.weekday() >= 5:
            continue
        pre, entry, close = window_bounds(day)
        i0 = idx.searchsorted(entry)
        if i0 >= len(idx) or idx[i0] != entry:
            continue
        i1 = idx.searchsorted(close)
        complete = last >= close - pd.Timedelta(minutes=5)
        if complete_only and not complete:
            continue
        bars = i1 - i0
        p0 = idx.searchsorted(pre)
        e = op[i0]
        pre_range = (hi[p0:i0].max() - lo[p0:i0].min()) / e if i0 > p0 else np.nan
        rng = (hi[i0:i1].max() - lo[i0:i1].min()) / e if bars > 0 else np.nan
        rows[pd.Timestamp(day)] = {"entry": e, "range": rng, "pre_range": pre_range, "bars": bars, "complete": complete}
    out = pd.DataFrame.from_dict(rows, orient="index").sort_index()
    if out.empty:  # nenhum dia com a barra das 13:30 (ex.: só barras diárias)
        return pd.DataFrame(columns=["entry", "range", "pre_range", "bars", "complete"])
    if complete_only:
        out = out[(out["bars"] >= MIN_BARS) & (out["range"] > 0)]
    return out


def features(win: pd.DataFrame, event_days: set[date]) -> pd.DataFrame:
    """Variáveis conhecidas na entrada de cada dia (só dias anteriores + a madrugada do próprio dia)."""
    lr = np.log(win["range"].where(win["range"] > 0))
    f = pd.DataFrame(index=win.index)
    f["d"] = lr.shift(1)
    f["w"] = lr.shift(1).rolling(5).mean()
    f["m"] = lr.shift(1).rolling(22).mean()
    f["pre"] = np.log(win["pre_range"].where(win["pre_range"] > 0))
    f["event"] = [1.0 if t.date() in event_days else 0.0 for t in win.index]
    f["target"] = lr
    return f


def fit_ols(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    A = np.column_stack([np.ones(len(X)), X])
    return np.linalg.lstsq(A, y, rcond=None)[0]


def predict(coef, X: np.ndarray) -> np.ndarray:
    coef = np.asarray(coef)
    return coef[0] + X @ coef[1:]


def block_bootstrap_mean_ci(values: np.ndarray, level: float, block: int = 20, resamples: int = 2000, seed: int = 7) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = len(values)
    starts = np.arange(max(1, n - block + 1))
    means = np.empty(resamples)
    for i in range(resamples):
        idx = np.concatenate([np.arange(s, s + block) for s in rng.choice(starts, size=int(np.ceil(n / block)))])[:n]
        means[i] = values[idx].mean()
    a = (1 - level) / 2
    return float(np.quantile(means, a)), float(np.quantile(means, 1 - a))


def forecast_today(m5: pd.DataFrame, model: dict, event_days: set[date], now: datetime) -> dict | None:
    """Previsão da janela de hoje, disponível a partir da barra das 13:30 UTC (precisa de 22 dias anteriores)."""
    d = _utc(m5)
    today = now.astimezone(NEW_YORK).date()
    pre, entry, close = window_bounds(today)
    if pd.Timestamp(now) < entry or entry not in d.index:
        return None
    hist = windows(d[d.index < entry])
    if len(hist) < 22:
        return None
    lr = np.log(hist["range"])
    i0 = d.index.searchsorted(entry)
    p0 = d.index.searchsorted(pre)
    e = float(d["open"].iloc[i0])
    pre_range = float((d["high"].iloc[p0:i0].max() - d["low"].iloc[p0:i0].min()) / e) if i0 > p0 else np.nan
    if not np.isfinite(pre_range) or pre_range <= 0:
        return None
    x = np.array([lr.iloc[-1], lr.iloc[-5:].mean(), lr.iloc[-22:].mean(), np.log(pre_range), 1.0 if today in event_days else 0.0])
    mid = float(predict(model["coef"], x[None, :])[0])
    so_far = d[(d.index >= entry) & (d.index < close)]
    done = (so_far["high"].max() - so_far["low"].min()) / e if not so_far.empty else 0.0
    return {"date": today.isoformat(), "entry_price": e, "close_utc": close.isoformat(),
            "expected_pct": float(np.exp(mid) * 100), "low80_pct": float(np.exp(mid + model["q10"]) * 100),
            "high80_pct": float(np.exp(mid + model["q90"]) * 100), "expected_points": float(np.exp(mid) * e),
            "low80_points": float(np.exp(mid + model["q10"]) * e), "high80_points": float(np.exp(mid + model["q90"]) * e),
            "so_far_pct": float(done * 100), "event": bool(x[4]), "closed": bool(d.index[-1] >= close - pd.Timedelta(minutes=5))}
