"""Dados do laboratório: barras M5 bid + spread, reamostragem causal e ATR."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

MARKET = Path(r"D:\OneB\market-data")
HONOR = MARKET / "mt5" / "HonorPro" / "synced-2026-09-25"
HONOR_UTC_OFFSET_HOURS = 3  # medido em abr-set/2026 (correlação 0,965 contra o Dukascopy)

DUKASCOPY_FILES = {
    "XAUUSD": MARKET / "dukascopy-xau-2019-2026" / "normalized" / "XAUUSD_M5_2019-03-01_2026-09-26.csv.gz",
    "NAS100": MARKET / "dukascopy-nas100-2019-2026" / "normalized" / "NAS100_M5_2019-03-01_2026-09-26.csv.gz",
    "SPX500": MARKET / "dukascopy-spx500-2019-2026" / "normalized" / "SPX500_M5_2019-03-01_2026-09-26.csv.gz",
    "EURUSD": MARKET / "dukascopy-eurusd-2019-2026" / "normalized" / "EURUSD_M5_2019-03-01_2026-09-26.csv.gz",
    "WTI": MARKET / "dukascopy-wti-2019-2026" / "normalized" / "WTI_M5_2019-03-01_2026-09-26.csv.gz",
}
HONOR_SPREAD = {"XAUUSD": ("XAUUSD.s", 0.01), "NAS100": ("US100.s", 0.1), "SPX500": ("US500.s", 0.1)}


def available_assets() -> list[str]:
    return [a for a, p in DUKASCOPY_FILES.items() if p.exists()]


def honor_hourly_spread(asset: str) -> dict[int, float]:
    """Mediana do spread HonorPro (em preço) por hora UTC; vazio se o símbolo não existir."""
    if asset not in HONOR_SPREAD:
        return {}
    symbol, point = HONOR_SPREAD[asset]
    files = sorted(HONOR.glob(f"{symbol}_M5_*.csv.gz"))
    if not files:
        return {}
    frame = pd.read_csv(files[-1], parse_dates=["timestamp"])
    utc = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_localize(None) - pd.Timedelta(hours=HONOR_UTC_OFFSET_HOURS)
    spread = frame["spread"].astype(float) * point
    return {int(h): float(v) for h, v in spread.groupby(utc.dt.hour).median().items()}


def load_m5(asset: str) -> tuple[pd.DataFrame, dict]:
    """M5 bid OHLC; coluna `spread` em PREÇO (custo conservador: maior entre Dukascopy e HonorPro)."""
    raw = pd.read_csv(DUKASCOPY_FILES[asset])
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True).dt.tz_localize(None)
    raw = raw.drop_duplicates("timestamp").sort_values("timestamp").set_index("timestamp")
    frame = pd.DataFrame({
        "open": raw["bid_open"], "high": raw["bid_high"], "low": raw["bid_low"], "close": raw["bid_close"],
        "duka_spread": raw["spread_open"].clip(lower=0), "tick_volume": raw.get("volume", 0),
    }).dropna(subset=["open", "high", "low", "close"])
    hourly = honor_hourly_spread(asset)
    floor = frame.index.hour.map(lambda h: hourly.get(int(h), 0.0)).to_numpy()
    frame["spread"] = np.maximum(frame["duka_spread"].to_numpy(), floor)
    median = float(frame["duka_spread"].median())
    meta = {"rows": len(frame), "median_duka_spread": median, "honor_spread_hours": len(hourly),
            "slippage_per_side": 0.25 * median, "commission_roundtrip": 0.25 * median}
    return frame, meta


def resample(m5: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Barras fechadas do timeframe; índice = ABERTURA. Use close_time() para o instante do sinal."""
    bars = m5.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return bars


def atr(bars: pd.DataFrame, period: int = 14) -> pd.Series:
    prev = bars["close"].shift()
    tr = pd.concat([bars["high"] - bars["low"], (bars["high"] - prev).abs(), (bars["low"] - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()
