"""Pure pandas implementations of common technical indicators.

All functions take a pandas Series/DataFrame with a DatetimeIndex and return
a Series aligned to the same index, so no external TA dependency is needed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(window=period, min_periods=period).mean()


def ema(close: pd.Series, period: int) -> pd.Series:
    return close.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    # avg_loss == 0 (no losses in window) -> RSI is 100; keep NaN where not enough data yet
    result = result.where(avg_loss != 0, 100.0)
    result[avg_gain.isna() | avg_loss.isna()] = np.nan
    return result


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "histogram": histogram})


def bollinger_bands(close: pd.Series, period: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    mid = sma(close, period)
    std = close.rolling(window=period, min_periods=period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return pd.DataFrame({"mid": mid, "upper": upper, "lower": lower})


def volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """Current volume / rolling average volume."""
    avg_vol = volume.rolling(window=period, min_periods=period).mean()
    return volume / avg_vol.replace(0, pd.NA)


def pct_change_over_window(close: pd.Series, periods: int = 1) -> pd.Series:
    return close.pct_change(periods=periods) * 100


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    previous_close = close.shift(1)
    ranges = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    )
    true_range = ranges.max(axis=1)
    return true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.DataFrame:
    """Wilder's DMI/ADX: directional movement (+DI/-DI) and trend strength (ADX).

    Needed by the regime engine (trend-strength input) and by the 13X /
    100 Pips proprietary indicators, which both key off the DI+/DI-/ADX
    structure.
    """
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    tr = pd.concat(
        [high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)

    atr_wilder = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr_wilder.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr_wilder.replace(0, np.nan)

    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
    adx_line = dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    return pd.DataFrame({"plus_di": plus_di, "minus_di": minus_di, "adx": adx_line})


def annualized_volatility(close: pd.Series, periods_per_year: int = 252, window: int = 20) -> pd.Series:
    returns = close.pct_change()
    return returns.rolling(window=window, min_periods=window).std() * np.sqrt(periods_per_year) * 100


def classic_pivot_points(high: float, low: float, close: float) -> dict[str, float]:
    """Classic floor-trader pivot points from the prior period's OHLC.

    Same formula a trading-desk morning briefing uses to mark intraday support/
    resistance (P, S1-S3, R1-R3) — the standard, reproducible alternative to a
    manually-drawn trendline.
    """
    pivot = (high + low + close) / 3
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)
    r3 = high + 2 * (pivot - low)
    s3 = low - 2 * (high - pivot)
    return {
        "pivot": round(pivot, 2),
        "r1": round(r1, 2),
        "r2": round(r2, 2),
        "r3": round(r3, 2),
        "s1": round(s1, 2),
        "s2": round(s2, 2),
        "s3": round(s3, 2),
    }


def swing_levels(history: pd.DataFrame, lookback: int = 20) -> dict[str, float | None]:
    """Recent swing high/low over `lookback` periods, plus the prior period's close.

    Used alongside pivot points to flag the nearest structural support/resistance
    (e.g. "20-day high") a level-based morning report would call out.
    """
    if history.empty or len(history) < 2:
        return {"swing_high": None, "swing_low": None, "prev_close": None}
    window = history.tail(lookback)
    return {
        "swing_high": round(float(window["high"].max()), 2),
        "swing_low": round(float(window["low"].min()), 2),
        "prev_close": round(float(history["close"].iloc[-2]), 2),
    }
