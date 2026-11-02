"""Regras clássicas de compra/venda, parametrizadas, para o laboratório de backtest."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app import indicators as ind


def atr(ohlcv: pd.DataFrame, period: int = 14) -> pd.Series:
    prev = ohlcv["close"].shift(1)
    tr = pd.concat(
        [ohlcv["high"] - ohlcv["low"], (ohlcv["high"] - prev).abs(), (ohlcv["low"] - prev).abs()], axis=1
    ).max(axis=1)
    return tr.rolling(period).mean()


@dataclass
class Rule:
    entry: pd.Series
    exit: pd.Series | None = None
    kwargs: dict = field(default_factory=dict)  # trail_mult / max_hold / stop_pct


def _state(on: pd.Series) -> Rule:
    """Regra 'estar posicionado enquanto a condição vale'."""
    return Rule(entry=on.fillna(False), exit=~on.fillna(False))


def buy_hold(d):
    return Rule(entry=pd.Series(True, index=d.index), exit=pd.Series(False, index=d.index))


def trend_sma(d, n=200):
    return _state(d["close"] > d["close"].rolling(n).mean())


def golden_cross(d, fast=50, slow=200):
    return _state(d["close"].rolling(fast).mean() > d["close"].rolling(slow).mean())


def rsi_reversion(d, period=14, low=30, high=50):
    r = ind.rsi(d["close"], period)
    return Rule(entry=r < low, exit=r > high)


def rsi2_trend(d, low=10, high=70, trend=200, **kw):
    c = d["close"]
    r = ind.rsi(c, 2)
    return Rule(entry=(r < low) & (c > c.rolling(trend).mean()), exit=r > high, kwargs=kw)


def bollinger_reversion(d, period=20, std=2.0):
    c = d["close"]
    bb = ind.bollinger_bands(c, period, std)
    return Rule(entry=c < bb["lower"], exit=c > bb["mid"])


def donchian(d, entry_n=20, exit_n=10):
    c = d["close"]
    return Rule(
        entry=c > d["high"].rolling(entry_n).max().shift(1),
        exit=c < d["low"].rolling(exit_n).min().shift(1),
    )


def macd_cross(d):
    m = ind.macd(d["close"])
    above = m["macd"] > m["signal"]
    return Rule(entry=above & ~above.shift(1, fill_value=False), exit=~above)


def momentum(d, lookback=126, trend=200):
    c = d["close"]
    return _state((c / c.shift(lookback) - 1 > 0) & (c > c.rolling(trend).mean()))


def volume_breakout(d, mult=2.0, hold=10):
    c = d["close"]
    vr = ind.volume_ratio(d["volume"], 20)
    return Rule(
        entry=(vr > mult) & (c > d["open"]) & (c > c.rolling(50).mean()),
        exit=None,
        kwargs={"max_hold": hold},
    )


STRATEGIES = {
    "Buy & Hold": buy_hold,
    "Tendência: preço > SMA200": trend_sma,
    "Golden cross 50/200": golden_cross,
    "Momentum 6m + SMA200": momentum,
    "Rompimento Donchian 20/10": donchian,
    "MACD cruzamento": macd_cross,
    "RSI14 < 30 (sai > 50)": rsi_reversion,
    "Bollinger inferior (sai na média)": bollinger_reversion,
    "RSI2 < 10 em alta (sai RSI2 > 70)": rsi2_trend,
    "Volume 2x + alta (10 dias)": volume_breakout,
}
