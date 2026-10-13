"""Estudo de eventos do calendário macro (pré-registro calendar_v1).

O preço num instante t é o fechamento da barra M5 que TERMINA em t (barra aberta
em t-5min). Sem essa barra exata o valor é ausente e o evento sai daquela janela.
Horários de evento estão em Nova York (horário de verão americano respeitado).
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

NEW_YORK = ZoneInfo("America/New_York")
WINDOWS = {"pre60": (-60, 0), "post5": (0, 5), "post30": (0, 30), "post120": (0, 120)}
CONTROL_DAYS = 20


def load_events(path: Path) -> list[tuple[str, pd.Timestamp]]:
    spec = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for kind, info in spec["events"].items():
        hh, mm = map(int, info["time_et"].split(":"))
        for d in info["dates"]:
            local = pd.Timestamp(f"{d} {hh:02d}:{mm:02d}").tz_localize(NEW_YORK)
            out.append((kind, local.tz_convert("UTC")))
    return sorted(out, key=lambda x: x[1])


def bar_end_series(m5: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Fechamento e spread indexados pelo FIM da barra (UTC)."""
    end = m5.index + pd.Timedelta(minutes=5)
    return pd.Series(m5["close"].to_numpy(), index=end), pd.Series(m5["spread"].to_numpy(), index=end)


def log_ret(close: pd.Series, t0: pd.Timestamp, a: int, b: int) -> float | None:
    p0, p1 = close.get(t0 + pd.Timedelta(minutes=a)), close.get(t0 + pd.Timedelta(minutes=b))
    if p0 is None or p1 is None or not (p0 > 0 and p1 > 0):
        return None
    return float(np.log(p1 / p0))


def control_times(t0: pd.Timestamp, event_days: set, n: int = CONTROL_DAYS) -> list[pd.Timestamp]:
    """Mesmo horário de Nova York nos n dias úteis anteriores sem evento da lista."""
    local = t0.tz_convert(NEW_YORK)
    out, day = [], local
    while len(out) < n:
        day = day - pd.Timedelta(days=1)
        if day.weekday() >= 5 or day.date() in event_days:
            continue
        out.append(pd.Timestamp(f"{day.date()} {local.strftime('%H:%M')}").tz_localize(NEW_YORK).tz_convert("UTC"))
    return out


def boot_median_ci(values: np.ndarray, resamples: int = 5000, seed: int = 7) -> tuple[float, float, np.ndarray]:
    rng = np.random.default_rng(seed)
    meds = np.median(values[rng.integers(0, len(values), size=(resamples, len(values)))], axis=1)
    return float(np.quantile(meds, 0.025)), float(np.quantile(meds, 0.975)), meds


def boot_mean_ci(values: np.ndarray, resamples: int = 5000, seed: int = 7) -> tuple[float, float, np.ndarray]:
    rng = np.random.default_rng(seed)
    means = values[rng.integers(0, len(values), size=(resamples, len(values)))].mean(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975)), means


def bh(pvals: dict[str, float], q: float = 0.05) -> dict[str, bool]:
    keys = sorted(pvals, key=pvals.get)
    m, cutoff = len(keys), 0
    for rank, k in enumerate(keys, start=1):
        if pvals[k] <= q * rank / m:
            cutoff = rank
    return {k: i < cutoff for i, k in enumerate(keys)}


def volatility(close: pd.Series, events: list[tuple[str, pd.Timestamp]], event_days: set) -> dict:
    """H1: razão |retorno| evento / mediana do controle, por tipo e janela."""
    out = {}
    for kind in sorted({k for k, _ in events}):
        per_window = {}
        for name, (a, b) in WINDOWS.items():
            ratios, years, dropped = [], [], 0
            for k, t0 in events:
                if k != kind:
                    continue
                r = log_ret(close, t0, a, b)
                ctrl = [log_ret(close, t, a, b) for t in control_times(t0, event_days)]
                ctrl = [abs(x) for x in ctrl if x is not None]
                if r is None or len(ctrl) < 10 or np.median(ctrl) == 0:
                    dropped += 1
                    continue
                ratios.append(abs(r) / float(np.median(ctrl)))
                years.append(t0.year)
            if len(ratios) < 10:
                per_window[name] = {"events": len(ratios), "dropped": dropped}
                continue
            arr = np.asarray(ratios)
            lo, hi, meds = boot_median_ci(arr)
            by_year = {str(y): round(float(np.median([r for r, yy in zip(ratios, years) if yy == y])), 2) for y in sorted(set(years))}
            per_window[name] = {"events": len(ratios), "dropped": dropped, "median_ratio": round(float(np.median(arr)), 2),
                                "ci95": [round(lo, 2), round(hi, 2)], "p_le_1": float((meds <= 1).mean()), "by_year": by_year}
        out[kind] = per_window
    return out


def direction(close: pd.Series, spread: pd.Series, events: list[tuple[str, pd.Timestamp]]) -> dict:
    """H2: retorno de +5 a +60 min no sentido dos primeiros 5 min, menos meio spread na entrada e na saída (bps)."""
    out = {}
    for kind in sorted({k for k, _ in events}):
        vals = []
        for k, t0 in events:
            if k != kind:
                continue
            first, post = log_ret(close, t0, 0, 5), log_ret(close, t0, 5, 60)
            t5, t60 = t0 + pd.Timedelta(minutes=5), t0 + pd.Timedelta(minutes=60)
            if first is None or post is None or first == 0 or t5 not in spread.index or t60 not in spread.index:
                continue
            cost = (spread[t5] / close[t5] + spread[t60] / close[t60]) / 2
            vals.append((np.sign(first) * post - cost) * 1e4)
        if len(vals) < 10:
            out[kind] = {"events": len(vals)}
            continue
        arr = np.asarray(vals)
        lo, hi, means = boot_mean_ci(arr)
        p_two = float(2 * min((means <= 0).mean(), (means >= 0).mean()))
        out[kind] = {"events": len(vals), "mean_bps": round(float(arr.mean()), 2), "ci95_bps": [round(lo, 2), round(hi, 2)],
                     "p_two_sided": p_two, "reading": "continuação" if lo > 0 else "reversão" if hi < 0 else "sem direção"}
    return out


def pre_fomc(close: pd.Series, fomc_days: list[date]) -> dict:
    """H3: 14:00 NY do pregão anterior -> 13:55 NY do dia; FOMC contra os demais pares de dias úteis."""
    def window(day: date) -> float | None:
        prev = pd.Timestamp(day) - pd.offsets.BDay(1)
        start = pd.Timestamp(f"{prev.date()} 14:00").tz_localize(NEW_YORK).tz_convert("UTC")
        end = pd.Timestamp(f"{day} 13:55").tz_localize(NEW_YORK).tz_convert("UTC")
        p0, p1 = close.get(start), close.get(end)
        return float(np.log(p1 / p0)) if p0 and p1 else None

    days = sorted({ts.tz_convert(NEW_YORK).date() for ts in close.index if ts.weekday() < 5})
    fomc_set = set(fomc_days)
    ev = [x for x in (window(d) for d in fomc_days) if x is not None]
    ctrl = [x for x in (window(d) for d in days if d not in fomc_set) if x is not None]
    if len(ev) < 10:
        return {"events": len(ev)}
    rng = np.random.default_rng(7)
    e, c = np.asarray(ev), np.asarray(ctrl)
    diffs = e[rng.integers(0, len(e), (5000, len(e)))].mean(axis=1) - c[rng.integers(0, len(c), (5000, len(c)))].mean(axis=1)
    lo, hi = float(np.quantile(diffs, 0.025)), float(np.quantile(diffs, 0.975))
    return {"events": len(ev), "control_days": len(ctrl), "fomc_mean_bps": round(float(e.mean() * 1e4), 2),
            "control_mean_bps": round(float(c.mean() * 1e4), 2), "diff_ci95_bps": [round(lo * 1e4, 2), round(hi * 1e4, 2)],
            "passed": lo > 0}
