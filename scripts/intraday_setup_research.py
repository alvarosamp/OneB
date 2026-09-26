"""Pesquisa intradiaria causal de setups para NQ/MNQ e GC/MGC/XAUUSD.

O modulo aceita CSVs normalizados ou exportacoes do MetaTrader 5. Todo sinal e
calculado no fechamento de uma barra e executado apenas na abertura da barra
seguinte. O holdout final nunca participa da escolha de parametros.

Exemplo:
    python scripts/intraday_setup_research.py \
      --market NQ=data/intraday/NQ_5m.csv \
      --market GC=data/intraday/GC_5m.csv
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from dataclasses import asdict, dataclass
from datetime import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, brier_score_loss, matthews_corrcoef
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

NY_TZ = "America/New_York"


@dataclass(frozen=True)
class InstrumentSpec:
    symbol: str
    point_value: float
    tick_size: float
    commission_per_side: float
    spread_ticks: float
    slippage_ticks_per_side: float
    session_open: str
    session_close: str
    overnight_start: str = "18:00"

    @property
    def tick_value(self) -> float:
        return self.point_value * self.tick_size

    @property
    def round_trip_cost(self) -> float:
        return 2 * self.commission_per_side + self.tick_value * (
            self.spread_ticks + 2 * self.slippage_ticks_per_side
        )


DEFAULT_SPECS = {
    "NQ": InstrumentSpec("NQ", 20.0, 0.25, 2.50, 1.0, 0.5, "09:30", "16:00"),
    "MNQ": InstrumentSpec("MNQ", 2.0, 0.25, 0.80, 1.0, 0.5, "09:30", "16:00"),
    # NAS100 CFD contract value is broker dependent; bid/ask comes from the source.
    "NAS100": InstrumentSpec("NAS100", 1.0, 0.10, 0.0, 0.0, 0.5, "09:30", "16:00"),
    # 07:00 e a janela de pesquisa documentada, nao uma afirmacao sobre pit hours.
    "GC": InstrumentSpec("GC", 100.0, 0.10, 2.50, 1.0, 0.5, "07:00", "13:30"),
    "MGC": InstrumentSpec("MGC", 10.0, 0.10, 1.20, 1.0, 0.5, "07:00", "13:30"),
    # XAUUSD is broker dependent. These values are only explicit placeholders.
    "XAUUSD": InstrumentSpec("XAUUSD", 1.0, 0.01, 0.0, 20.0, 2.0, "07:00", "13:30"),
}


@dataclass(frozen=True)
class ResearchConfig:
    source_timezone: str = NY_TZ
    opening_ranges_minutes: tuple[int, ...] = (15, 30)
    stop_atr: tuple[float, ...] = (0.75, 1.0, 1.25)
    reward_r: tuple[float, ...] = (1.5, 2.0, 3.0)
    max_hold_minutes: tuple[int, ...] = (30, 60, 120)
    holdout_fraction: float = 0.20
    development_folds: int = 5
    min_sessions: int = 250
    min_holdout_trades: int = 30
    final_candidates: int = 12
    entry_finalists_per_family: int = 3
    seed: int = 20260912


def _clock(value: str) -> time:
    return time.fromisoformat(value)


def _stable_id(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:12]


def load_intraday_csv(path: Path, source_timezone: str = NY_TZ) -> pd.DataFrame:
    """Load common CSV/MT5 formats and normalize the index to New York time."""
    raw = pd.read_csv(path, sep=None, engine="python")
    raw.columns = [str(c).strip().lower().replace("<", "").replace(">", "") for c in raw.columns]
    # Vendor exports frequently encode the timezone in the timestamp header
    # (for example, ``timestamp ET``).  Treat it as metadata, not as a
    # different field, while the caller remains responsible for declaring the
    # source timezone.
    if "timestamp" not in raw.columns:
        timestamp_alias = next(
            (column for column in raw.columns if column.startswith("timestamp ")),
            None,
        )
        if timestamp_alias:
            raw = raw.rename(columns={timestamp_alias: "timestamp"})
    if "date" in raw.columns and "time" in raw.columns:
        raw["timestamp"] = raw["date"].astype(str) + " " + raw["time"].astype(str)
    elif "datetime" in raw.columns:
        raw["timestamp"] = raw["datetime"]
    elif "timestamp" not in raw.columns and "time" in raw.columns:
        raw["timestamp"] = raw["time"]
    required = {"timestamp", "open", "high", "low", "close"}
    missing = sorted(required - set(raw.columns))
    if missing:
        raise ValueError(f"CSV sem colunas obrigatorias: {missing}")
    volume_source = next((c for c in ("volume", "tick_volume", "tickvol", "vol") if c in raw.columns), None)
    quote_columns = [
        column for column in (
            "bid_open", "bid_high", "bid_low", "bid_close",
            "ask_open", "ask_high", "ask_low", "ask_close",
        ) if column in raw.columns
    ]
    columns = ["timestamp", "open", "high", "low", "close"] + ([volume_source] if volume_source else []) + quote_columns
    bars = raw[columns].copy()
    if volume_source:
        bars = bars.rename(columns={volume_source: "volume"})
    else:
        bars["volume"] = 0.0
    if pd.api.types.is_numeric_dtype(bars["timestamp"]):
        magnitude = float(pd.to_numeric(bars["timestamp"], errors="coerce").dropna().median())
        unit = "ms" if magnitude >= 1e11 else "s"
        bars["timestamp"] = pd.to_datetime(bars["timestamp"], unit=unit, utc=True, errors="raise")
    else:
        bars["timestamp"] = pd.to_datetime(bars["timestamp"], errors="raise")
    for column in ["open", "high", "low", "close", "volume", *quote_columns]:
        bars[column] = pd.to_numeric(bars[column], errors="coerce")
    bars = bars.dropna(subset=["timestamp", "open", "high", "low", "close"])
    index = pd.DatetimeIndex(bars.pop("timestamp"))
    if index.tz is None:
        index = index.tz_localize(source_timezone, ambiguous="NaT", nonexistent="shift_forward")
    index = index.tz_convert(NY_TZ)
    bars.index = index
    bars = bars[~bars.index.isna()].sort_index()
    return bars[~bars.index.duplicated(keep="last")]


def resample_bars(bars: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """Aggregate completed lower-timeframe bars without backfilling future values."""
    aggregation = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    for prefix in ("bid", "ask"):
        if f"{prefix}_open" in bars.columns:
            aggregation.update(
                {
                    f"{prefix}_open": "first", f"{prefix}_high": "max",
                    f"{prefix}_low": "min", f"{prefix}_close": "last",
                }
            )
    return bars.resample(f"{minutes}min", label="left", closed="left").agg(aggregation).dropna(
        subset=["open", "high", "low", "close"]
    )


def research_timeframes(symbol: str, native_minutes: int) -> list[int]:
    desired = [1, 5, 10, 15] if symbol in {"NQ", "MNQ", "NAS100"} else [10]
    valid = [minutes for minutes in desired if minutes >= native_minutes and minutes % native_minutes == 0]
    return valid or [native_minutes]


def strategy_catalog() -> list[dict[str, Any]]:
    return [
        {"family": "gold_fakeout", "instruments": ["GC", "MGC", "XAUUSD"], "source": "user_document", "logic": "20-bar liquidity sweep, reclaim, MA1000 and 1-2 confirmation bars", "stop": "sweep extreme plus 0.15 ATR", "targets": "1.5R, 2R, 3R"},
        {"family": "gold_mean_reversion", "instruments": ["GC", "MGC", "XAUUSD"], "source": "user_document", "logic": "Bollinger extension plus RSI with ADX regime filter", "stop": "0.75-1.25 ATR", "targets": "Bollinger mid, VWAP or fixed R"},
        {"family": "gold_trend_pullback", "instruments": ["GC", "MGC", "XAUUSD"], "source": "user_document", "logic": "EMA trend, ADX/DI, pullback and close reclaim", "stop": "0.75-1.25 ATR", "targets": "1.5R, 2R, 3R"},
        {"family": "gold_volatility_squeeze", "instruments": ["GC", "MGC", "XAUUSD"], "source": "user_document", "logic": "low Bollinger width rank followed by price and volatility expansion", "stop": "0.75-1.25 ATR", "targets": "1.5R, 2R, 3R"},
        {"family": "nasdaq_13x_sweep", "instruments": ["NQ", "MNQ", "NAS100"], "source": "user_document", "logic": "11/13/15-bar liquidity sweep and reclaim", "stop": "sweep extreme plus 0.10-0.25 ATR", "targets": "1.5R-2.5R; 12/24-bar time stop"},
        {"family": "nasdaq_13x_ema_atr", "instruments": ["NQ", "MNQ", "NAS100"], "source": "user_document", "logic": "EMA13 distance of 1-2 ATR followed by 0.25/0.50 ATR reclaim", "stop": "0.75-1.25 ATR", "targets": "1.5R-2.5R"},
        {"family": "nasdaq_13x_momentum_failure", "instruments": ["NQ", "MNQ", "NAS100"], "source": "user_document", "logic": "13-bar extreme, structural reclaim and RSI non-confirmation", "stop": "0.75-1.25 ATR", "targets": "1.5R, 2R, 3R"},
        {"family": "opening_breakout", "instruments": ["NQ", "MNQ", "GC", "MGC", "XAUUSD"], "source": "research_extension", "logic": "15/30-minute opening range breakout with momentum", "stop": "ATR", "targets": "fixed R"},
        {"family": "opening_fade", "instruments": ["NQ", "MNQ", "GC", "MGC", "XAUUSD"], "source": "research_extension", "logic": "opening range false breakout in first two hours", "stop": "ATR", "targets": "fixed R"},
        {"family": "vwap_reversion", "instruments": ["NQ", "MNQ", "GC", "MGC", "XAUUSD"], "source": "research_extension", "logic": "ATR-normalized VWAP extension plus RSI", "stop": "ATR", "targets": "fixed R"},
        {"family": "overnight_breakout", "instruments": ["NQ", "MNQ", "GC", "MGC", "XAUUSD"], "source": "research_extension", "logic": "overnight high/low breakout in first two hours", "stop": "ATR", "targets": "fixed R"},
    ]


def diagnose_bars(bars: pd.DataFrame) -> dict[str, Any]:
    if bars.empty:
        return {"status": "BLOCKED", "issues": ["EMPTY_DATA"], "rows": 0}
    delta = bars.index.to_series().diff().dt.total_seconds().div(60)
    positive = delta[(delta > 0) & (delta <= 240)]
    interval = float(positive.median()) if not positive.empty else None
    invalid_ohlc = (
        (bars["high"] < bars[["open", "close", "low"]].max(axis=1))
        | (bars["low"] > bars[["open", "close", "high"]].min(axis=1))
        | (bars[["open", "high", "low", "close"]] <= 0).any(axis=1)
    )
    expected = interval or 1.0
    irregular = float((positive.sub(expected).abs() > max(0.01, expected * 0.05)).mean()) if len(positive) else 1.0
    issues = []
    if invalid_ohlc.any():
        issues.append(f"INVALID_OHLC:{int(invalid_ohlc.sum())}")
    if irregular > 0.05:
        issues.append(f"IRREGULAR_INTERVAL_RATIO:{irregular:.3f}")
    if bars["volume"].fillna(0).le(0).all():
        issues.append("NO_USABLE_VOLUME")
    return {
        "status": "BLOCKED" if invalid_ohlc.any() or interval is None else "PASS",
        "issues": issues,
        "rows": int(len(bars)),
        "start": bars.index.min().isoformat(),
        "end": bars.index.max().isoformat(),
        "bar_minutes": interval,
        "duplicate_timestamps": int(bars.index.duplicated().sum()),
        "invalid_ohlc": int(invalid_ohlc.sum()),
        "volume_coverage": round(float(bars["volume"].fillna(0).gt(0).mean()), 4),
    }


def _true_range(bars: pd.DataFrame) -> pd.Series:
    previous = bars["close"].shift(1)
    return pd.concat(
        [(bars["high"] - bars["low"]), (bars["high"] - previous).abs(), (bars["low"] - previous).abs()],
        axis=1,
    ).max(axis=1)


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.DataFrame:
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    true_range = pd.concat(
        [high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1
    ).max(axis=1)
    average_range = true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / average_range.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / average_range.replace(0, np.nan)
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
    return pd.DataFrame(
        {"plus_di": plus_di, "minus_di": minus_di, "adx": dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()}
    )


def build_features(bars: pd.DataFrame, spec: InstrumentSpec, opening_minutes: int) -> pd.DataFrame:
    """Build close-of-bar features. Signals may use the current completed bar."""
    frame = bars.copy()
    local = frame.index.tz_convert(NY_TZ)
    frame["session_date"] = pd.Series(local.date, index=frame.index)
    open_clock, close_clock = _clock(spec.session_open), _clock(spec.session_close)
    clock = pd.Series(local.time, index=frame.index)
    frame["in_rth"] = (clock >= open_clock) & (clock < close_clock)
    frame["minutes_from_open"] = (
        local.hour * 60 + local.minute - (open_clock.hour * 60 + open_clock.minute)
    ).astype(float)
    frame["atr14"] = _true_range(frame).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    frame["ema13"] = frame["close"].ewm(span=13, adjust=False, min_periods=13).mean()
    frame["ema20"] = frame["close"].ewm(span=20, adjust=False, min_periods=20).mean()
    frame["ema50"] = frame["close"].ewm(span=50, adjust=False, min_periods=50).mean()
    frame["ma1000"] = frame["close"].rolling(1000, min_periods=1000).mean()
    delta = frame["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    frame["rsi14"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    frame["roc5"] = frame["close"].pct_change(5)
    frame["realized_vol20"] = frame["close"].pct_change().rolling(20).std()
    frame["relative_volume50"] = frame["volume"] / frame["volume"].rolling(50).median().replace(0, np.nan)
    dmi = _adx(frame["high"], frame["low"], frame["close"], 14)
    frame["adx14"] = dmi["adx"]
    frame["plus_di"] = dmi["plus_di"]
    frame["minus_di"] = dmi["minus_di"]
    frame["bb_mid20"] = frame["close"].rolling(20, min_periods=20).mean()
    bb_std = frame["close"].rolling(20, min_periods=20).std()
    frame["bb_upper20"] = frame["bb_mid20"] + 2 * bb_std
    frame["bb_lower20"] = frame["bb_mid20"] - 2 * bb_std
    frame["bb_width20"] = (4 * bb_std) / frame["bb_mid20"].replace(0, np.nan)
    frame["bb_width_rank200"] = frame["bb_width20"].rolling(200, min_periods=100).rank(pct=True)

    rth = frame[frame["in_rth"]].copy()
    group = rth.groupby("session_date", sort=False)
    typical = (rth["high"] + rth["low"] + rth["close"]) / 3
    cumulative_volume = group["volume"].cumsum()
    cumulative_pv = (typical * rth["volume"]).groupby(rth["session_date"]).cumsum()
    rth["vwap"] = cumulative_pv / cumulative_volume.replace(0, np.nan)
    opening = rth["minutes_from_open"].between(0, opening_minutes - 1, inclusive="both")
    rth["opening_high"] = rth["high"].where(opening).groupby(rth["session_date"]).cummax()
    rth["opening_low"] = rth["low"].where(opening).groupby(rth["session_date"]).cummin()
    rth[["opening_high", "opening_low"]] = group[["opening_high", "opening_low"]].ffill()

    session_summary = group.agg(session_high=("high", "max"), session_low=("low", "min"), session_close=("close", "last"))
    previous = session_summary.shift(1).rename(
        columns={"session_high": "prior_session_high", "session_low": "prior_session_low", "session_close": "prior_session_close"}
    )
    rth = rth.join(previous, on="session_date")

    overnight_rows: list[dict[str, Any]] = []
    overnight_start = _clock(spec.overnight_start)
    for session_date in pd.Index(rth["session_date"].unique()):
        date_value = pd.Timestamp(session_date)
        start = pd.Timestamp.combine((date_value - pd.Timedelta(days=1)).date(), overnight_start).tz_localize(NY_TZ)
        end = pd.Timestamp.combine(date_value.date(), open_clock).tz_localize(NY_TZ)
        sample = frame.loc[(frame.index >= start) & (frame.index < end)]
        overnight_rows.append(
            {
                "session_date": session_date,
                "overnight_high": sample["high"].max() if not sample.empty else np.nan,
                "overnight_low": sample["low"].min() if not sample.empty else np.nan,
            }
        )
    rth = rth.join(pd.DataFrame(overnight_rows).set_index("session_date"), on="session_date")
    rth["vwap_distance_atr"] = (rth["close"] - rth["vwap"]) / rth["atr14"]
    rth["gap_atr"] = (rth["open"] - rth["prior_session_close"]) / rth["atr14"]
    rth["trend_strength_atr"] = (rth["ema20"] - rth["ema50"]) / rth["atr14"]
    rth["opening_width_atr"] = (rth["opening_high"] - rth["opening_low"]) / rth["atr14"]
    rth["overnight_width_atr"] = (rth["overnight_high"] - rth["overnight_low"]) / rth["atr14"]
    rth["prior_range_atr"] = (rth["prior_session_high"] - rth["prior_session_low"]) / rth["atr14"]
    rth["vol_ratio"] = rth["realized_vol20"] / rth["realized_vol20"].rolling(250, min_periods=50).median().shift(1)
    direction = np.select([rth["trend_strength_atr"] > 0.5, rth["trend_strength_atr"] < -0.5], ["up", "down"], default="flat")
    volatility = np.where(rth["vol_ratio"] > 1.0, "high_vol", "low_vol")
    rth["regime"] = pd.Series(direction, index=rth.index).astype(str) + "_" + pd.Series(volatility, index=rth.index).astype(str)
    minutes = rth["minutes_from_open"].clip(lower=0)
    rth["time_sin"] = np.sin(2 * np.pi * minutes / 390)
    rth["time_cos"] = np.cos(2 * np.pi * minutes / 390)
    return rth


def setup_grid(config: ResearchConfig, symbol: str | None = None) -> list[dict[str, Any]]:
    """Entry hypotheses, including the user's seven named strategy families."""
    setups: list[dict[str, Any]] = []
    for opening in config.opening_ranges_minutes:
        for buffer_ticks in (0.0, 1.0):
            setups.extend(
                [
                    {"family": "opening_breakout", "opening_minutes": opening, "buffer_ticks": buffer_ticks},
                    {"family": "opening_fade", "opening_minutes": opening, "buffer_ticks": buffer_ticks},
                ]
            )
    for threshold in (0.5, 1.0, 1.5):
        setups.append({"family": "vwap_reversion", "opening_minutes": 30, "distance_atr": threshold})
    for buffer_ticks in (0.0, 1.0):
        setups.append({"family": "overnight_breakout", "opening_minutes": 30, "buffer_ticks": buffer_ticks})
    if symbol in {"GC", "MGC", "XAUUSD"}:
        for lookback in (18, 20, 22):
            for confirmation in (1, 2):
                setups.append(
                    {
                        "family": "gold_fakeout",
                        "lookback": lookback,
                        "ma_period": 1000,
                        "confirmation_bars": confirmation,
                        "stop_buffer_atr": 0.15,
                        "structural_stop": True,
                    }
                )
        for band_std in (1.8, 2.0, 2.2):
            for rsi_entry in (25, 30, 35):
                for adx_max in (20, 25):
                    for target_mode in ("risk", "bb_mid", "vwap"):
                        setups.append(
                            {
                                "family": "gold_mean_reversion",
                                "window": 20,
                                "band_std": band_std,
                                "rsi_entry": rsi_entry,
                                "adx_max": adx_max,
                                "target_mode": target_mode,
                            }
                        )
        for fast, slow in ((15, 40), (20, 50), (25, 60)):
            for adx_min in (18, 22):
                setups.append(
                    {"family": "gold_trend_pullback", "fast": fast, "slow": slow, "adx_min": adx_min}
                )
        for width_rank in (0.15, 0.25):
            setups.append({"family": "gold_volatility_squeeze", "width_rank": width_rank})
    if symbol in {"NQ", "MNQ", "NAS100"}:
        for lookback in (11, 13, 15):
            for stop_buffer in (0.10, 0.15, 0.25):
                for confirmation in (0, 1):
                    for hold_bars in (12, 24):
                        setups.append(
                            {
                                "family": "nasdaq_13x_sweep",
                                "lookback": lookback,
                                "confirmation_bars": confirmation,
                                "stop_buffer_atr": stop_buffer,
                                "structural_stop": True,
                                "hold_bars": hold_bars,
                                "reward_options": (1.5, 2.0, 2.5),
                            }
                        )
        for threshold in (1.0, 1.5, 2.0):
            for reclaim in (0.25, 0.50):
                setups.append(
                    {
                        "family": "nasdaq_13x_ema_atr",
                        "distance_atr": threshold,
                        "reclaim_atr": reclaim,
                        "reward_options": (1.5, 2.0, 2.5),
                    }
                )
        for momentum_lookback in (3, 5):
            for rsi_improvement in (0.0, 3.0):
                setups.append(
                    {
                        "family": "nasdaq_13x_momentum_failure",
                        "lookback": 13,
                        "momentum_lookback": momentum_lookback,
                        "rsi_improvement": rsi_improvement,
                    }
                )
    return setups


def setup_signals(frame: pd.DataFrame, spec: InstrumentSpec, setup: dict[str, Any]) -> tuple[pd.Series, pd.Series]:
    family = setup["family"]
    after_opening = frame["minutes_from_open"] >= setup.get("opening_minutes", 0)
    first_two_hours = frame["minutes_from_open"].between(setup.get("opening_minutes", 0), 120)
    buffer = setup.get("buffer_ticks", 0.0) * spec.tick_size
    if family == "opening_breakout":
        long_signal = after_opening & (frame["close"] > frame["opening_high"] + buffer) & (frame["roc5"] > 0)
        short_signal = after_opening & (frame["close"] < frame["opening_low"] - buffer) & (frame["roc5"] < 0)
    elif family == "opening_fade":
        long_signal = first_two_hours & (frame["low"] < frame["opening_low"] - buffer) & (frame["close"] > frame["opening_low"])
        short_signal = first_two_hours & (frame["high"] > frame["opening_high"] + buffer) & (frame["close"] < frame["opening_high"])
    elif family == "vwap_reversion":
        threshold = setup["distance_atr"]
        long_signal = after_opening & (frame["vwap_distance_atr"] <= -threshold) & (frame["rsi14"] <= 35)
        short_signal = after_opening & (frame["vwap_distance_atr"] >= threshold) & (frame["rsi14"] >= 65)
    elif family == "overnight_breakout":
        long_signal = first_two_hours & (frame["close"] > frame["overnight_high"] + buffer) & (frame["roc5"] > 0)
        short_signal = first_two_hours & (frame["close"] < frame["overnight_low"] - buffer) & (frame["roc5"] < 0)
    elif family == "gold_fakeout":
        lookback = setup["lookback"]
        confirmation = setup["confirmation_bars"]
        prior_low = frame["low"].shift(1).rolling(lookback, min_periods=lookback).min()
        prior_high = frame["high"].shift(1).rolling(lookback, min_periods=lookback).max()
        sweep_long = (frame["low"] < prior_low) & (frame["close"] > prior_low) & (frame["close"] > frame["ma1000"])
        sweep_short = (frame["high"] > prior_high) & (frame["close"] < prior_high) & (frame["close"] < frame["ma1000"])
        long_signal, short_signal = sweep_long.shift(confirmation), sweep_short.shift(confirmation)
        sweep_low, sweep_high = prior_low.shift(confirmation), prior_high.shift(confirmation)
        for offset in range(confirmation):
            long_signal &= frame["close"].shift(offset) > sweep_low
            short_signal &= frame["close"].shift(offset) < sweep_high
        in_window = frame["minutes_from_open"].between(0, 240)
        long_signal &= in_window
        short_signal &= in_window
    elif family == "gold_mean_reversion":
        mid = frame["close"].rolling(setup["window"], min_periods=setup["window"]).mean()
        deviation = frame["close"].rolling(setup["window"], min_periods=setup["window"]).std()
        lower, upper = mid - setup["band_std"] * deviation, mid + setup["band_std"] * deviation
        long_signal = (frame["close"] < lower) & (frame["rsi14"] <= setup["rsi_entry"]) & (frame["adx14"] <= setup["adx_max"])
        short_signal = (frame["close"] > upper) & (frame["rsi14"] >= 100 - setup["rsi_entry"]) & (frame["adx14"] <= setup["adx_max"])
    elif family == "gold_trend_pullback":
        fast = frame["close"].ewm(span=setup["fast"], adjust=False, min_periods=setup["fast"]).mean()
        slow = frame["close"].ewm(span=setup["slow"], adjust=False, min_periods=setup["slow"]).mean()
        long_signal = (
            (fast > slow) & (frame["plus_di"] > frame["minus_di"]) & (frame["adx14"] >= setup["adx_min"])
            & (frame["low"] <= fast) & (frame["close"] > fast) & (frame["close"].shift(1) <= fast.shift(1))
        )
        short_signal = (
            (fast < slow) & (frame["minus_di"] > frame["plus_di"]) & (frame["adx14"] >= setup["adx_min"])
            & (frame["high"] >= fast) & (frame["close"] < fast) & (frame["close"].shift(1) >= fast.shift(1))
        )
    elif family == "gold_volatility_squeeze":
        compressed = frame["bb_width_rank200"].shift(1) <= setup["width_rank"]
        long_signal = compressed & (frame["close"] > frame["bb_upper20"]) & (frame["bb_width20"] > frame["bb_width20"].shift(1))
        short_signal = compressed & (frame["close"] < frame["bb_lower20"]) & (frame["bb_width20"] > frame["bb_width20"].shift(1))
    elif family == "nasdaq_13x_sweep":
        lookback = setup["lookback"]
        confirmation = setup["confirmation_bars"]
        prior_low = frame["low"].shift(1).rolling(lookback, min_periods=lookback).min()
        prior_high = frame["high"].shift(1).rolling(lookback, min_periods=lookback).max()
        long_signal = ((frame["low"] < prior_low) & (frame["close"] > prior_low)).shift(confirmation)
        short_signal = ((frame["high"] > prior_high) & (frame["close"] < prior_high)).shift(confirmation)
        if confirmation:
            long_signal &= frame["close"] > prior_low.shift(confirmation)
            short_signal &= frame["close"] < prior_high.shift(confirmation)
    elif family == "nasdaq_13x_ema_atr":
        distance = (frame["close"] - frame["ema13"]) / frame["atr14"]
        long_signal = (distance.shift(1) <= -setup["distance_atr"]) & (distance - distance.shift(1) >= setup["reclaim_atr"])
        short_signal = (distance.shift(1) >= setup["distance_atr"]) & (distance.shift(1) - distance >= setup["reclaim_atr"])
    elif family == "nasdaq_13x_momentum_failure":
        lookback = setup["lookback"]
        momentum = setup["momentum_lookback"]
        prior_low = frame["low"].shift(1).rolling(lookback, min_periods=lookback).min()
        prior_high = frame["high"].shift(1).rolling(lookback, min_periods=lookback).max()
        prior_rsi_low = frame["rsi14"].shift(1).rolling(momentum, min_periods=momentum).min()
        prior_rsi_high = frame["rsi14"].shift(1).rolling(momentum, min_periods=momentum).max()
        improvement = setup["rsi_improvement"]
        long_signal = (frame["low"] < prior_low) & (frame["close"] > prior_low) & (frame["rsi14"] >= prior_rsi_low + improvement)
        short_signal = (frame["high"] > prior_high) & (frame["close"] < prior_high) & (frame["rsi14"] <= prior_rsi_high - improvement)
    else:
        raise ValueError(f"Familia desconhecida: {family}")
    return long_signal.fillna(False), short_signal.fillna(False)


def _exit_price(side: int, open_price: float, stop: float, target: float, high: float, low: float) -> tuple[float, str] | None:
    stop_hit = low <= stop if side == 1 else high >= stop
    target_hit = high >= target if side == 1 else low <= target
    if stop_hit:  # ordem pessimista se stop e alvo aparecem na mesma barra
        return (min(open_price, stop) if side == 1 else max(open_price, stop), "stop")
    if target_hit:
        return (max(open_price, target) if side == 1 else min(open_price, target), "target")
    return None


def simulate(
    frame: pd.DataFrame,
    spec: InstrumentSpec,
    long_signal: pd.Series,
    short_signal: pd.Series,
    stop_atr: float | None,
    reward_r: float | None,
    max_hold_minutes: int,
    setup_id: str,
    allowed_dates: set | None = None,
    cost_multiplier: float = 1.0,
    setup: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    bar_minutes = frame.attrs.get("bar_minutes") or diagnose_bars(frame)["bar_minutes"] or 1
    max_bars = max(1, int(max_hold_minutes / bar_minutes))
    trades: list[dict[str, Any]] = []
    long_values = long_signal.fillna(False).to_numpy(dtype=bool)
    short_values = short_signal.fillna(False).to_numpy(dtype=bool)
    session_values = frame["session_date"].to_numpy()
    atr_values = frame["atr14"].to_numpy(dtype=float)
    open_values = frame["open"].to_numpy(dtype=float)
    high_values = frame["high"].to_numpy(dtype=float)
    low_values = frame["low"].to_numpy(dtype=float)
    close_values = frame["close"].to_numpy(dtype=float)
    candidate_mask = pd.Series((long_values != short_values) & np.isfinite(atr_values), index=frame.index)
    if allowed_dates is not None:
        candidate_mask &= pd.Series(np.isin(session_values, list(allowed_dates)), index=frame.index)
    candidate_positions = np.flatnonzero(candidate_mask.to_numpy())
    observed_quotes = all(f"{prefix}_{field}" in frame.columns for prefix in ("bid", "ask") for field in ("open", "high", "low", "close"))
    quote_values = {
        f"{prefix}_{field}": frame[f"{prefix}_{field}"].to_numpy(dtype=float)
        for prefix in ("bid", "ask") for field in ("open", "high", "low", "close")
    } if observed_quotes else {}
    next_available = 0
    for i in candidate_positions:
        if i < next_available or i >= len(frame) - 1:
            continue
        session_date = session_values[i]
        side = 1 if long_values[i] and not short_values[i] else -1 if short_values[i] and not long_values[i] else 0
        if side == 0 or not np.isfinite(atr_values[i]):
            continue
        entry_pos = i + 1
        if session_values[entry_pos] != session_date:
            continue
        if observed_quotes:
            entry = float(quote_values["ask_open" if side == 1 else "bid_open"][entry_pos])
            entry += side * spec.slippage_ticks_per_side * spec.tick_size * cost_multiplier
        else:
            entry = float(open_values[entry_pos])
        setup = setup or {}
        if setup.get("structural_stop"):
            sweep_pos = i - int(setup.get("confirmation_bars", 0))
            if sweep_pos < 0:
                continue
            stop_buffer = float(atr_values[i]) * float(setup["stop_buffer_atr"])
            stop = float(low_values[sweep_pos]) - stop_buffer if side == 1 else float(high_values[sweep_pos]) + stop_buffer
            risk_points = side * (entry - stop)
        else:
            risk_points = float(atr_values[i]) * float(stop_atr)
            stop = entry - side * risk_points
        if not np.isfinite(risk_points) or risk_points <= 0:
            continue
        target_mode = setup.get("target_mode", "risk")
        if target_mode == "bb_mid":
            target = float(frame["bb_mid20"].iloc[i])
        elif target_mode == "vwap":
            target = float(frame["vwap"].iloc[i])
        else:
            target = entry + side * risk_points * float(reward_r)
        if not np.isfinite(target) or side * (target - entry) <= 0:
            continue
        exit_pos = entry_pos
        exit_price = entry
        reason = "session_close"
        for j in range(entry_pos, min(len(frame), entry_pos + max_bars)):
            if session_values[j] != session_date:
                break
            exit_pos = j
            execution_prefix = "bid" if side == 1 else "ask"
            exit_price = float(quote_values[f"{execution_prefix}_close"][j]) if observed_quotes else float(close_values[j])
            hit = _exit_price(
                side,
                float(quote_values[f"{execution_prefix}_open"][j]) if observed_quotes else float(open_values[j]),
                stop,
                target,
                float(quote_values[f"{execution_prefix}_high"][j]) if observed_quotes else float(high_values[j]),
                float(quote_values[f"{execution_prefix}_low"][j]) if observed_quotes else float(low_values[j]),
            )
            if hit:
                exit_price, reason = hit
                break
            if j == entry_pos + max_bars - 1:
                reason = "time"
        if observed_quotes:
            exit_price -= side * spec.slippage_ticks_per_side * spec.tick_size * cost_multiplier
        gross = side * (exit_price - entry) * spec.point_value
        modeled_cost = 2 * spec.commission_per_side if observed_quotes else spec.round_trip_cost
        net = gross - modeled_cost * cost_multiplier
        trades.append(
            {
                "setup_id": setup_id,
                "decision_time": frame.index[i].isoformat(),
                "entry_time": frame.index[entry_pos].isoformat(),
                "exit_time": frame.index[exit_pos].isoformat(),
                "session_date": str(session_date),
                "side": "long" if side == 1 else "short",
                "entry": round(entry, 6),
                "exit": round(exit_price, 6),
                "stop": round(stop, 6),
                "target": round(target, 6),
                "exit_reason": reason,
                "execution_model": "observed_bid_ask" if observed_quotes else "modeled_spread",
                "net_pnl": round(net, 4),
                "net_r": round(net / (risk_points * spec.point_value), 6),
            }
        )
        next_available = exit_pos + 1
    return trades


def metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {"trades": 0, "net_pnl": 0.0, "expectancy": None, "expectancy_r": None, "profit_factor": None, "win_rate": None, "sharpe": None, "max_drawdown": 0.0, "p_value": None}
    pnl = pd.Series([t["net_pnl"] for t in trades], dtype=float)
    by_day = pd.DataFrame(trades).groupby("session_date")["net_pnl"].sum()
    equity = by_day.cumsum()
    drawdown = equity - equity.cummax()
    standard_deviation = by_day.std(ddof=1)
    losses = -pnl[pnl < 0].sum()
    test = stats.ttest_1samp(pnl, 0, alternative="greater") if len(pnl) >= 3 and pnl.std(ddof=1) > 1e-12 else None
    return {
        "trades": int(len(pnl)),
        "net_pnl": round(float(pnl.sum()), 2),
        "expectancy": round(float(pnl.mean()), 2),
        "expectancy_r": round(float(pd.Series([t["net_r"] for t in trades]).mean()), 4),
        "profit_factor": round(float(pnl[pnl > 0].sum() / losses), 3) if losses > 0 else None,
        "win_rate": round(float((pnl > 0).mean()), 4),
        "sharpe": round(float(by_day.mean() / standard_deviation * math.sqrt(252)), 3) if standard_deviation > 0 else None,
        "max_drawdown": round(float(drawdown.min()), 2),
        "p_value": round(float(test.pvalue), 6) if test is not None and np.isfinite(test.pvalue) else None,
    }


def _bh_adjust(values: pd.Series) -> pd.Series:
    result = pd.Series(np.nan, index=values.index, dtype=float)
    valid = values.dropna().sort_values()
    if valid.empty:
        return result
    adjusted = (valid * len(valid) / np.arange(1, len(valid) + 1)).iloc[::-1].cummin().iloc[::-1].clip(upper=1)
    result.loc[adjusted.index] = adjusted
    return result


def _folds(dates: list, count: int) -> list[tuple[set, set]]:
    if len(dates) < count + 2:
        return []
    initial = max(1, int(len(dates) * 0.40))
    remainder = dates[initial:]
    chunks = [list(chunk) for chunk in np.array_split(remainder, count) if len(chunk)]
    output = []
    for chunk in chunks:
        validation = set(chunk)
        train = {date for date in dates if date < chunk[0]}
        output.append((train, validation))
    return output


def _candidate_definitions(
    config: ResearchConfig, bar_minutes: int, symbol: str, setups: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    definitions = []
    for setup in setups or setup_grid(config, symbol):
        stops = (None,) if setup.get("structural_stop") else config.stop_atr
        rewards = setup.get("reward_options", config.reward_r)
        if setup.get("target_mode") in {"bb_mid", "vwap"}:
            rewards = (None,)
        holds = (int(setup["hold_bars"] * bar_minutes),) if "hold_bars" in setup else config.max_hold_minutes
        for stop in stops:
            for reward in rewards:
                for hold in holds:
                    if hold >= bar_minutes:
                        definition = {"setup": setup, "stop_atr": stop, "reward_r": reward, "max_hold_minutes": hold}
                        definition["setup_id"] = _stable_id(definition)
                        definitions.append(definition)
    return definitions


META_FEATURES = [
    "vwap_distance_atr", "gap_atr", "rsi14", "roc5", "realized_vol20", "relative_volume50",
    "minutes_from_open", "time_sin", "time_cos", "atr14", "trend_strength_atr", "opening_width_atr",
    "overnight_width_atr", "prior_range_atr", "vol_ratio",
]


def _meta_model(name: str, seed: int) -> Pipeline:
    transformer = ColumnTransformer([("numeric", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), META_FEATURES)])
    if name == "logistic_l1":
        model = LogisticRegression(l1_ratio=1.0, solver="liblinear", C=0.1, class_weight="balanced", max_iter=3000, random_state=seed)
    else:
        model = RandomForestClassifier(n_estimators=400, max_depth=4, min_samples_leaf=20, class_weight="balanced_subsample", random_state=seed, n_jobs=1)
    return Pipeline([("features", transformer), ("model", model)])


def meta_label_evaluation(frame: pd.DataFrame, trades: list[dict[str, Any]], development_dates: set, holdout_dates: set, seed: int) -> list[dict[str, Any]]:
    if not trades:
        return []
    lookup = frame[META_FEATURES].copy()
    rows = []
    for trade in trades:
        timestamp = pd.Timestamp(trade["decision_time"])
        if timestamp not in lookup.index:
            continue
        row = lookup.loc[timestamp].to_dict()
        row.update({"session_date": pd.Timestamp(trade["session_date"]).date(), "net_pnl": trade["net_pnl"], "label": int(trade["net_pnl"] > 0)})
        rows.append(row)
    samples = pd.DataFrame(rows).sort_values("session_date")
    train = samples[samples["session_date"].isin(development_dates)]
    test = samples[samples["session_date"].isin(holdout_dates)]
    if len(train) < 60 or len(test) < 20 or train["label"].nunique() < 2:
        return [{"status": "NEEDS_MORE_DATA", "development_events": len(train), "holdout_events": len(test)}]
    output = []
    for name in ("logistic_l1", "random_forest"):
        oof = pd.Series(np.nan, index=train.index, dtype=float)
        initial = max(30, int(len(train) * 0.40))
        for chunk in np.array_split(np.arange(initial, len(train)), 3):
            if not len(chunk):
                continue
            prior = np.arange(0, int(chunk[0]))
            if len(prior) < 30 or train.iloc[prior]["label"].nunique() < 2:
                continue
            fold_model = _meta_model(name, seed)
            fold_model.fit(train.iloc[prior], train.iloc[prior]["label"])
            oof.iloc[chunk] = fold_model.predict_proba(train.iloc[chunk])[:, 1]
        threshold_scores = []
        for threshold in (0.50, 0.55, 0.60):
            accepted = oof.ge(threshold) & oof.notna()
            pnl = train.loc[accepted, "net_pnl"]
            threshold_scores.append(
                {"threshold": threshold, "accepted": int(len(pnl)), "expectancy": float(pnl.mean()) if len(pnl) >= 10 else -np.inf}
            )
        selected = max(threshold_scores, key=lambda row: (row["expectancy"], row["accepted"]))
        threshold = float(selected["threshold"])
        model = _meta_model(name, seed)
        model.fit(train, train["label"])
        probability = model.predict_proba(test)[:, 1]
        accepted = probability >= threshold
        pnl = test.loc[accepted, "net_pnl"]
        predicted = probability >= 0.5
        output.append(
            {
                "status": "EXPERIMENTAL",
                "model": name,
                "threshold": threshold,
                "threshold_selected_on": "development_walk_forward_oof",
                "development_oof_accepted": selected["accepted"],
                "development_oof_expectancy": round(selected["expectancy"], 2) if np.isfinite(selected["expectancy"]) else None,
                "accepted_trades": int(accepted.sum()),
                "net_pnl": round(float(pnl.sum()), 2),
                "expectancy": round(float(pnl.mean()), 2) if len(pnl) else None,
                "balanced_accuracy": round(float(balanced_accuracy_score(test["label"], predicted)), 4),
                "mcc": round(float(matthews_corrcoef(test["label"], predicted)), 4),
                "brier": round(float(brier_score_loss(test["label"], probability)), 5),
            }
        )
    return output


def research_market(bars: pd.DataFrame, spec: InstrumentSpec, config: ResearchConfig) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    diagnostic = diagnose_bars(bars)
    if diagnostic["status"] == "BLOCKED":
        return {"symbol": spec.symbol, "status": "BLOCKED", "diagnostic": diagnostic}, {}
    session_probe = build_features(bars, spec, config.opening_ranges_minutes[0])
    sessions = sorted(pd.unique(session_probe["session_date"]))
    if len(sessions) < config.min_sessions:
        diagnostic["issues"] = [*diagnostic["issues"], f"INSUFFICIENT_SESSIONS:{len(sessions)}<{config.min_sessions}"]
        return {"symbol": spec.symbol, "status": "NEEDS_MORE_DATA", "diagnostic": diagnostic, "sessions": len(sessions)}, {}
    holdout_count = max(1, int(len(sessions) * config.holdout_fraction))
    development_dates, holdout_dates = sessions[:-holdout_count], sessions[-holdout_count:]
    folds = _folds(development_dates, config.development_folds)
    session_probe.attrs["bar_minutes"] = diagnostic["bar_minutes"]
    feature_cache: dict[int, pd.DataFrame] = {config.opening_ranges_minutes[0]: session_probe}
    signal_cache: dict[tuple[int, str], tuple[pd.Series, pd.Series]] = {}

    def cached_frame(opening: int) -> pd.DataFrame:
        if opening not in feature_cache:
            feature_cache[opening] = build_features(bars, spec, opening)
            feature_cache[opening].attrs["bar_minutes"] = diagnostic["bar_minutes"]
        return feature_cache[opening]

    def cached_signals(opening: int, setup: dict[str, Any]) -> tuple[pd.Series, pd.Series]:
        key = (opening, _stable_id(setup))
        if key not in signal_cache:
            signal_cache[key] = setup_signals(cached_frame(opening), spec, setup)
        return signal_cache[key]

    screening_rows = []
    for setup in setup_grid(config, spec.symbol):
        opening = setup.get("opening_minutes", 30)
        frame = cached_frame(opening)
        signals = cached_signals(opening, setup)
        stop = None if setup.get("structural_stop") else 1.0
        hold = int(setup.get("hold_bars", max(1, 60 / diagnostic["bar_minutes"])) * diagnostic["bar_minutes"])
        fold_expectancy, all_trades = [], []
        for _, validation in folds:
            trades = simulate(frame, spec, *signals, stop, 2.0, hold, f"screen-{_stable_id(setup)}", validation, setup=setup)
            result = metrics(trades)
            all_trades.extend(trades)
            if result["expectancy"] is not None:
                fold_expectancy.append(result["expectancy"])
        screening_rows.append(
            {
                "setup": setup,
                "family": setup["family"],
                "positive_folds": int(sum(value > 0 for value in fold_expectancy)),
                "median_fold_expectancy": round(float(np.median(fold_expectancy)), 2) if fold_expectancy else None,
                **metrics(all_trades),
            }
        )
    screening = pd.DataFrame(screening_rows).sort_values(
        ["positive_folds", "median_fold_expectancy", "sharpe", "trades"], ascending=[False, False, False, False]
    )
    selected_setups = (
        screening.groupby("family", sort=False, group_keys=False).head(config.entry_finalists_per_family)["setup"].tolist()
    )
    definitions = _candidate_definitions(config, int(diagnostic["bar_minutes"]), spec.symbol, selected_setups)
    development_rows = []
    for definition in definitions:
        opening = definition["setup"].get("opening_minutes", 30)
        frame = cached_frame(opening)
        long_signal, short_signal = cached_signals(opening, definition["setup"])
        fold_expectancy = []
        fold_trades = []
        for _, validation in folds:
            trades = simulate(
                frame, spec, long_signal, short_signal, definition["stop_atr"], definition["reward_r"],
                definition["max_hold_minutes"], definition["setup_id"], validation, setup=definition["setup"],
            )
            result = metrics(trades)
            fold_trades.extend(trades)
            if result["expectancy"] is not None:
                fold_expectancy.append(result["expectancy"])
        aggregate = metrics(fold_trades)
        development_rows.append(
            {
                **definition,
                "positive_folds": int(sum(value > 0 for value in fold_expectancy)),
                "median_fold_expectancy": round(float(np.median(fold_expectancy)), 2) if fold_expectancy else None,
                **aggregate,
            }
        )
    development = pd.DataFrame(development_rows)
    development["eligible"] = (development["trades"] >= config.min_holdout_trades) & (development["positive_folds"] >= 3)
    development = development.sort_values(["eligible", "positive_folds", "median_fold_expectancy", "sharpe", "trades"], ascending=[False, False, False, False, False])
    finalists = development.head(config.final_candidates)
    holdout_rows, all_top_trades = [], []
    for definition in finalists.to_dict(orient="records"):
        setup = definition["setup"]
        opening = setup.get("opening_minutes", 30)
        frame = feature_cache[opening]
        signals = signal_cache[(opening, _stable_id(setup))]
        trades = simulate(
            frame, spec, *signals, definition["stop_atr"], definition["reward_r"],
            int(definition["max_hold_minutes"]), definition["setup_id"], set(holdout_dates), setup=setup,
        )
        for trade in trades:
            trade["family"] = setup["family"]
        all_top_trades.extend(trades)
        holdout_rows.append({"setup_id": definition["setup_id"], "family": setup["family"], "definition": {k: definition[k] for k in ("setup", "stop_atr", "reward_r", "max_hold_minutes")}, **metrics(trades)})
    holdout = pd.DataFrame(holdout_rows)
    holdout["q_bh"] = _bh_adjust(holdout["p_value"])
    holdout["status"] = np.where(
        (holdout["trades"] >= config.min_holdout_trades) & (holdout["expectancy"].fillna(0) > 0) & (holdout["q_bh"].fillna(1) <= 0.10),
        "APPROVED_FOR_PAPER_TRADING",
        np.where(holdout["trades"] < config.min_holdout_trades, "NEEDS_MORE_DATA", "EXPERIMENTAL"),
    )
    holdout = holdout.sort_values(["status", "q_bh", "expectancy"], ascending=[True, True, False])
    best_id = str(finalists.iloc[0]["setup_id"])
    best_trades = [trade for trade in all_top_trades if trade["setup_id"] == best_id]
    best_definition = finalists.iloc[0]
    opening = best_definition["setup"].get("opening_minutes", 30)
    best_frame = feature_cache[opening]
    best_signals = signal_cache[(opening, _stable_id(best_definition["setup"]))]
    complete_best_trades = simulate(
        best_frame, spec, *best_signals, best_definition["stop_atr"], best_definition["reward_r"],
        int(best_definition["max_hold_minutes"]), best_id, setup=best_definition["setup"],
    )
    meta = meta_label_evaluation(best_frame, complete_best_trades, set(development_dates), set(holdout_dates), config.seed)
    cost_rows = []
    for multiplier in (1.0, 1.5, 2.0):
        trades = simulate(
            best_frame, spec, *best_signals, best_definition["stop_atr"], best_definition["reward_r"],
            int(best_definition["max_hold_minutes"]), best_id, set(holdout_dates), multiplier,
            setup=best_definition["setup"],
        )
        cost_rows.append({"cost_multiplier": multiplier, "round_trip_cost": round(spec.round_trip_cost * multiplier, 2), **metrics(trades)})
    regime_rows = []
    if best_trades:
        annotated = pd.DataFrame(best_trades)
        annotated["regime"] = annotated["decision_time"].map(
            lambda value: best_frame.loc[pd.Timestamp(value), "regime"] if pd.Timestamp(value) in best_frame.index else "unknown"
        )
        for regime, sample in annotated.groupby("regime"):
            regime_rows.append({"regime": regime, **metrics(sample.to_dict(orient="records"))})
    report = {
        "symbol": spec.symbol,
        "status": "COMPLETE",
        "diagnostic": diagnostic,
        "sessions": len(sessions),
        "development": {"start": str(development_dates[0]), "end": str(development_dates[-1]), "sessions": len(development_dates)},
        "holdout": {"start": str(holdout_dates[0]), "end": str(holdout_dates[-1]), "sessions": len(holdout_dates)},
        "instrument": asdict(spec) | {"tick_value": spec.tick_value, "round_trip_cost": spec.round_trip_cost},
        "entry_hypotheses_screened": len(screening),
        "entry_hypotheses_tuned": len(selected_setups),
        "candidates_tested": len(definitions),
        "approved": int((holdout["status"] == "APPROVED_FOR_PAPER_TRADING").sum()),
        "meta_labeling": meta,
    }
    tables = {
        "entry_screening": screening,
        "development": development,
        "holdout": holdout,
        # Export every untouched-holdout finalist so stability checks can be
        # reproduced without rerunning or silently selecting on the holdout.
        "trades": pd.DataFrame(all_top_trades),
        "meta_labeling": pd.DataFrame(meta),
        "cost_sensitivity": pd.DataFrame(cost_rows),
        "regime_holdout": pd.DataFrame(regime_rows),
    }
    return report, tables


def _load_config(path: Path | None) -> ResearchConfig:
    if path is None:
        return ResearchConfig()
    payload = json.loads(path.read_text(encoding="utf-8"))
    for name in ("opening_ranges_minutes", "stop_atr", "reward_r", "max_hold_minutes"):
        if name in payload:
            payload[name] = tuple(payload[name])
    return ResearchConfig(**payload)


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _render_report(results: list[dict[str, Any]], config: ResearchConfig) -> str:
    lines = [
        "# Pesquisa intradiaria de setups — Nasdaq e ouro",
        "",
        "Sinais usam somente candles concluidos; entradas ocorrem na abertura seguinte. Stops ambiguos sao avaliados primeiro e toda posicao e encerrada dentro da sessao.",
        "",
        f"Minimo exigido: {config.min_sessions} sessoes; holdout final: {config.holdout_fraction:.0%}; custo modelado por ticks, slippage e comissao do instrumento.",
        "",
    ]
    for result in results:
        lines.extend([f"## {result['symbol']}", "", f"Status: **{result['status']}**.", ""])
        diagnostic = result["diagnostic"]
        lines.append(f"Barras: {diagnostic.get('rows', 0)}; intervalo: {diagnostic.get('bar_minutes')}; problemas: {', '.join(diagnostic.get('issues', [])) or 'nenhum'}." )
        lines.append("")
        if result["status"] == "COMPLETE":
            lines.append(f"Sessoes: {result['sessions']}; combinacoes testadas: {result['candidates_tested']}; aprovadas: {result['approved']}.")
            lines.append("")
    lines.extend([
        "## Catalogo implementado",
        "",
    ])
    for item in strategy_catalog():
        lines.append(f"- `{item['family']}` ({', '.join(item['instruments'])}): {item['logic']}.")
    lines.extend([
        "",
        "## Interpretacao",
        "",
        "NEEDS_MORE_DATA ou BLOCKED nao e um resultado negativo da estrategia: significa que nao existe amostra suficiente para estimar sua vantagem. Nenhum setup deve ser promovido sem um holdout completo e custos calibrados no feed/corretora reais.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pesquisa intradiaria causal de NQ/MNQ/GC/MGC/XAUUSD")
    parser.add_argument("--market", action="append", default=[], help="SYMBOL=caminho.csv; pode ser repetido")
    parser.add_argument("--config", type=Path, default=Path("configs/intraday_setup_research.json"))
    parser.add_argument("--output", type=Path, default=Path("output/intraday_setup_research"))
    parser.add_argument("--source-timezone", default=None, help="Fuso de timestamps sem timezone")
    parser.add_argument(
        "--only-native",
        action="store_true",
        help="Pesquisa somente o timeframe do arquivo, sem criar M10/M15 adicionais",
    )
    args = parser.parse_args()
    config = _load_config(args.config if args.config.exists() else None)
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    inputs = []
    for value in args.market:
        symbol, separator, path = value.partition("=")
        if not separator or not path:
            raise ValueError("Use --market SYMBOL=caminho.csv")
        symbol = symbol.upper()
        if symbol not in DEFAULT_SPECS:
            raise ValueError(f"Instrumento sem especificacao: {symbol}")
        inputs.append((symbol, Path(path)))
    if not inputs:
        inputs = [("NQ", Path("data/intraday/NQ_5m.csv")), ("GC", Path("data/intraday/GC_5m.csv"))]
    results = []
    for symbol, path in inputs:
        if not path.exists():
            results.append({"symbol": symbol, "status": "BLOCKED", "diagnostic": {"status": "BLOCKED", "rows": 0, "bar_minutes": None, "issues": [f"MISSING_FILE:{path}"]}})
            continue
        bars = load_intraday_csv(path, args.source_timezone or config.source_timezone)
        native = diagnose_bars(bars).get("bar_minutes")
        if native is None:
            result, tables = research_market(bars, DEFAULT_SPECS[symbol], config)
            result["source_file"] = str(path.resolve())
            results.append(result)
            continue
        timeframes = [int(native)] if args.only_native else research_timeframes(symbol, int(native))
        for timeframe in timeframes:
            study_bars = bars if timeframe == int(native) else resample_bars(bars, timeframe)
            result, tables = research_market(study_bars, DEFAULT_SPECS[symbol], config)
            result["source_file"] = str(path.resolve())
            result["timeframe_minutes"] = timeframe
            results.append(result)
            for name, table in tables.items():
                table.to_csv(output / f"{symbol}_{timeframe}m_{name}.csv", index=False)
    payload = {"config": asdict(config), "strategy_catalog": strategy_catalog(), "markets": results}
    results_path = output / "results.json"
    report_path = output / "report.md"
    results_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    report_path.write_text(_render_report(results, config), encoding="utf-8")
    manifest = {
        "python": platform.python_version(),
        "packages": {"pandas": pd.__version__, "numpy": np.__version__},
        "script": {"path": str(Path(__file__).resolve()), "sha256": _file_hash(Path(__file__))},
        "config": {"path": str(args.config.resolve()), "sha256": _file_hash(args.config)} if args.config.exists() else None,
        "inputs": [
            {"symbol": symbol, "path": str(path.resolve()), "sha256": _file_hash(path)}
            for symbol, path in inputs if path.exists()
        ],
        "results_sha256": _file_hash(results_path),
        "report_sha256": _file_hash(report_path),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
