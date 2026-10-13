"""Famílias de regras do lab_v1 (congeladas no pré-registro).

Todas causais: o sinal usa só barras fechadas e é carimbado no FECHAMENTO da
barra. Só cruzamentos "frescos" geram sinal (a condição passar a valer nesta
barra), para não repetir o mesmo evento a cada barra.
Cada sinal: {opportunity_id, at, direction, stop, target, target_r, max_hold_minutes}.
"""
from __future__ import annotations

from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.lab.data import atr, resample

NEW_YORK = ZoneInfo("America/New_York")
LONDON = ZoneInfo("Europe/London")
TF = {"H1": ("1h", 60), "M15": ("15min", 15)}


def _signals(name: str, bars: pd.DataFrame, long_mask, short_mask, a: pd.Series, minutes: int,
             stop_atr: float, target_atr: float, hold_hours: float) -> list[dict]:
    out = []
    close = bars["close"]
    for side, mask in ((1, long_mask), (-1, short_mask)):
        for opened in bars.index[mask.fillna(False).to_numpy()]:
            at_atr = a.loc[opened]
            if not np.isfinite(at_atr) or at_atr <= 0:
                continue
            ref = float(close.loc[opened])
            out.append({
                "opportunity_id": f"{name}:{opened.isoformat()}:{side}",
                "at": (opened + pd.Timedelta(minutes=minutes)).isoformat(),
                "direction": "long" if side == 1 else "short",
                "stop": ref - side * stop_atr * at_atr, "target": ref + side * target_atr * at_atr,
                "target_r": None, "max_hold_minutes": int(hold_hours * 60),
            })
    out.sort(key=lambda s: s["at"])
    return out


def _fresh(cond: pd.Series) -> pd.Series:
    cond = cond.fillna(False)
    return cond & ~cond.shift(1, fill_value=False)


def f1_donchian(m5: pd.DataFrame, n: int) -> list[dict]:
    rule, minutes = TF["H1"]
    bars = resample(m5, rule)
    a = atr(bars)
    hi = bars["high"].shift(1).rolling(n, min_periods=n).max()
    lo = bars["low"].shift(1).rolling(n, min_periods=n).min()
    return _signals(f"F1_donchian_{n}", bars, _fresh(bars["close"] > hi), _fresh(bars["close"] < lo), a, minutes, 1.5, 3.0, 72)


def f2_ema_cross(m5: pd.DataFrame, fast: int, slow: int) -> list[dict]:
    rule, minutes = TF["H1"]
    bars = resample(m5, rule)
    a = atr(bars)
    ef = bars["close"].ewm(span=fast, adjust=False, min_periods=fast).mean()
    es = bars["close"].ewm(span=slow, adjust=False, min_periods=slow).mean()
    return _signals(f"F2_ema_{fast}_{slow}", bars, _fresh(ef > es), _fresh(ef < es), a, minutes, 2.0, 4.0, 120)


def f3_bollinger_reversion(m5: pd.DataFrame, z: float) -> list[dict]:
    rule, minutes = TF["M15"]
    bars = resample(m5, rule)
    a = atr(bars)
    mid = bars["close"].rolling(20, min_periods=20).mean()
    sd = bars["close"].rolling(20, min_periods=20).std()
    return _signals(f"F3_boll_{z}", bars, _fresh(bars["close"] < mid - z * sd), _fresh(bars["close"] > mid + z * sd),
                    a, minutes, 1.5, 1.0, 8)


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return 100 - 100 / (1 + up / down.replace(0, np.nan))


def f4_rsi2_pullback(m5: pd.DataFrame, threshold: int) -> list[dict]:
    rule, minutes = TF["H1"]
    bars = resample(m5, rule)
    a = atr(bars)
    r = _rsi(bars["close"], 2)
    sma = bars["close"].rolling(200, min_periods=200).mean()
    long_ = _fresh(r < threshold) & (bars["close"] > sma)
    short = _fresh(r > 100 - threshold) & (bars["close"] < sma)
    return _signals(f"F4_rsi2_{threshold}", bars, long_, short, a, minutes, 2.0, 1.0, 24)


def f5_squeeze(m5: pd.DataFrame, width_pct: int) -> list[dict]:
    rule, minutes = TF["H1"]
    bars = resample(m5, rule)
    a = atr(bars)
    mid = bars["close"].rolling(20, min_periods=20).mean()
    sd = bars["close"].rolling(20, min_periods=20).std()
    upper, lower = mid + 2 * sd, mid - 2 * sd
    width = (upper - lower) / mid
    # Percentil da largura ATUAL entre as 120 larguras anteriores (janela de 121; só passado + agora).
    rank = width.rolling(121, min_periods=121).apply(lambda w: (w[:-1] <= w[-1]).mean() * 100, raw=True)
    squeeze = rank <= width_pct
    return _signals(f"F5_squeeze_{width_pct}", bars, _fresh(bars["close"] > upper) & squeeze,
                    _fresh(bars["close"] < lower) & squeeze, a, minutes, 1.5, 3.0, 48)


def f6_opening_range(m5: pd.DataFrame, range_minutes: int, asset: str) -> list[dict]:
    tz, hh, mm = (NEW_YORK, 9, 30) if asset in ("NAS100", "SPX500") else (LONDON, 8, 0)
    local = m5.index.tz_localize("UTC").tz_convert(tz)
    frame = m5.assign(local_date=local.date, local_min=local.hour * 60 + local.minute)
    open_min = hh * 60 + mm
    out = []
    for day, g in frame.groupby("local_date", sort=True):
        rng = g[(g.local_min >= open_min) & (g.local_min < open_min + range_minutes)]
        if len(rng) < range_minutes // 5:
            continue
        top, bottom = float(rng["high"].max()), float(rng["low"].min())
        height = top - bottom
        if height <= 0:
            continue
        after = g[(g.local_min >= open_min + range_minutes) & (g.local_min < open_min + range_minutes + 180)]
        for opened, row in after.iterrows():
            side = 1 if row["close"] > top else -1 if row["close"] < bottom else 0
            if side == 0:
                continue
            ref = float(row["close"])
            out.append({"opportunity_id": f"F6_orb_{range_minutes}:{opened.isoformat()}", "at": (opened + pd.Timedelta(minutes=5)).isoformat(),
                        "direction": "long" if side == 1 else "short", "stop": bottom if side == 1 else top,
                        "target": ref + side * 2 * height, "target_r": None, "max_hold_minutes": 360})
            break  # 1 trade por dia
    return out


def f7_intraday_momentum(m5: pd.DataFrame, signal_window: str) -> list[dict]:
    a15 = atr(resample(m5, "15min"))
    local = m5.index.tz_localize("UTC").tz_convert(NEW_YORK)
    frame = m5.assign(local_date=local.date, local_min=local.hour * 60 + local.minute)
    closes = frame.groupby("local_date")
    prev_close = None
    out = []
    for day, g in closes:
        def price_at(minute: int) -> float | None:
            bar = g[g.local_min == minute]  # barra que ABRE nesse minuto; usamos o fechamento da anterior
            prior = g[g.local_min < minute]
            return float(prior["close"].iloc[-1]) if not prior.empty and not bar.empty else None
        p0930, p1000, p1500, p1600 = price_at(570), price_at(600), price_at(900), price_at(960)
        if signal_window == "first30":
            base, sig = prev_close, p1000
        else:
            base, sig = p0930, p1500
        if p1600 is not None:
            today_close = p1600
        else:
            today_close = None
        if base is not None and sig is not None and p1500 is not None and sig != base:
            entry_open = g[g.local_min == 900].index
            if len(entry_open):
                opened = entry_open[0]
                at = opened  # fechamento da barra 14:55 = 15:00
                at_atr = a15.asof(at - pd.Timedelta(minutes=15))
                if np.isfinite(at_atr) and at_atr > 0:
                    side = 1 if sig > base else -1
                    out.append({"opportunity_id": f"F7_mom_{signal_window}:{opened.isoformat()}", "at": at.isoformat(),
                                "direction": "long" if side == 1 else "short", "stop": p1500 - side * 1.5 * at_atr,
                                "target": p1500 + side * 10 * at_atr, "target_r": None, "max_hold_minutes": 60})
        prev_close = today_close if today_close is not None else prev_close
    return out


def _asof(values: pd.Series, bars_minutes: int, at: pd.DatetimeIndex) -> pd.Series:
    """Último valor de barra JÁ FECHADA (abertura + duração <= instante) em cada instante `at`."""
    known = pd.Series(values.to_numpy(), index=values.index + pd.Timedelta(minutes=bars_minutes)).dropna()
    pos = known.index.searchsorted(at, side="right") - 1
    out = np.where(pos >= 0, known.to_numpy()[np.clip(pos, 0, None)], np.nan) if len(known) else np.full(len(at), np.nan)
    return pd.Series(out, index=at)


def f8_duck(m5: pd.DataFrame, target_atr: float, period: int = 60) -> list[dict]:
    """Duck Duck Duck v4, sinal objetivo mínimo (emenda de 10/10/2026 ao lab_v1).

    Direção: último H4 E último H1 fechados do mesmo lado da SMA60 do próprio timeframe.
    Gatilho: fechamento M5 cruza a SMA60 do M5 na direção da tendência (cruzamento fresco).
    H4 em blocos UTC 00/04/08/12/16/20. Stop 1,5 x ATR(14) do H1; alvo `target_atr` x ATR(H1); 48 h.
    """
    close_time = m5.index + pd.Timedelta(minutes=5)
    side = {}
    for rule, minutes in (("4h", 240), ("1h", 60)):
        bars = resample(m5, rule)
        diff = bars["close"] - bars["close"].rolling(period, min_periods=period).mean()
        side[rule] = np.sign(_asof(diff, minutes, close_time).to_numpy())
    h1 = resample(m5, "1h")
    a = pd.Series(_asof(atr(h1), 60, close_time).to_numpy(), index=m5.index)
    above = (m5["close"] > m5["close"].rolling(period, min_periods=period).mean()).astype(float)
    above[m5["close"].rolling(period, min_periods=period).mean().isna()] = np.nan
    trend = pd.Series(np.where(side["4h"] == side["1h"], side["4h"], 0), index=m5.index)
    long_ = _fresh(above == 1) & (trend == 1)
    short = _fresh(above == 0) & (trend == -1)
    return _signals(f"F8_duck_t{target_atr:g}", m5, long_, short, a, 5, 1.5, target_atr, 48)


def candidates(asset: str) -> dict:
    """Os 16 candidatos do ativo, na ordem do pré-registro (F8 por emenda de 10/10/2026)."""
    return {
        "F1_donchian_20": lambda m: f1_donchian(m, 20),
        "F1_donchian_55": lambda m: f1_donchian(m, 55),
        "F2_ema_20_50": lambda m: f2_ema_cross(m, 20, 50),
        "F2_ema_50_200": lambda m: f2_ema_cross(m, 50, 200),
        "F3_boll_2.0": lambda m: f3_bollinger_reversion(m, 2.0),
        "F3_boll_2.5": lambda m: f3_bollinger_reversion(m, 2.5),
        "F4_rsi2_5": lambda m: f4_rsi2_pullback(m, 5),
        "F4_rsi2_10": lambda m: f4_rsi2_pullback(m, 10),
        "F5_squeeze_10": lambda m: f5_squeeze(m, 10),
        "F5_squeeze_20": lambda m: f5_squeeze(m, 20),
        "F6_orb_15": lambda m: f6_opening_range(m, 15, asset),
        "F6_orb_30": lambda m: f6_opening_range(m, 30, asset),
        "F7_mom_first30": lambda m: f7_intraday_momentum(m, "first30"),
        "F7_mom_open_to_1500": lambda m: f7_intraday_momentum(m, "open_to_1500"),
        "F8_duck_t2": lambda m: f8_duck(m, 2.0),
        "F8_duck_t4": lambda m: f8_duck(m, 4.0),
    }
