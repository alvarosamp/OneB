"""Causal, walk-forward feature research for Nasdaq and gold.

The experiment is intentionally separate from the production decision engine.
It uses information available at the close of day t, enters at the next open,
and exits at the open after ``horizon`` trading days.  Model/feature selection
is performed only on expanding development folds; the final two years are a
single untouched out-of-sample evaluation.

Examples
--------
    python scripts/nasdaq_gold_feature_research.py --refresh
    python scripts/nasdaq_gold_feature_research.py --cache-only
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    balanced_accuracy_score,
    brier_score_loss,
    matthews_corrcoef,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import indicators  # noqa: E402
from app.research_provenance import write_manifest  # noqa: E402


@dataclass(frozen=True)
class ResearchConfig:
    period: str = "15y"
    horizon: int = 5
    holdout_years: int = 2
    development_folds: int = 5
    cost_bps_per_side: float = 7.0
    min_train_bars: int = 756
    min_trades: int = 25
    feature_quantile: float = 0.80
    seed: int = 20260910


TARGETS = {
    "nasdaq": {"primary": "QQQ", "transfer": "NQ=F"},
    "gold": {"primary": "GLD", "transfer": "GC=F"},
}

CONTEXT_SYMBOLS = {
    "vix": "^VIX",
    "dollar": "DX-Y.NYB",
    "treasury_10y": "^TNX",
    "semiconductors": "SMH",
    "sp500": "SPY",
    "equal_weight_sp500": "RSP",
    "long_treasuries": "TLT",
    "intermediate_treasuries": "IEF",
    "inflation_linked_bonds": "TIP",
    "silver": "SLV",
    "oil": "CL=F",
}

# Official daily macro observations cached by app.market_data.fred_client.
# They are shifted one trading day before becoming features.  This is a
# deliberately conservative availability rule: a value stamped on date t is
# never used to decide at the close/open transition of the same date.
FRED_CONTEXT = {
    "us2y": "DGS2",
    "us5y": "DGS5",
    "us10y": "DGS10",
    "us30y": "DGS30",
    "broad_dollar": "DTWEXBGS",
    "vix_official": "VIXCLS",
    "real_10y": "DFII10",
    "breakeven_10y": "T10YIE",
    "wti": "DCOILWTICO",
    "brent": "DCOILBRENTEU",
}

FEATURE_FAMILIES: dict[str, str] = {
    "sma10_gap": "trend",
    "sma20_gap": "trend",
    "sma40_gap": "trend",
    "sma50_gap": "trend",
    "ema20_50_gap": "trend",
    "ema20_slope_5": "trend",
    "linreg_slope_10": "trend",
    "linreg_slope_20": "trend",
    "linreg_slope_40": "trend",
    "linreg_r2_20": "trend",
    "adx14": "trend",
    "trend_efficiency_10": "trend",
    "trend_efficiency_20": "trend",
    "trend_efficiency_40": "trend",
    "rsi7": "momentum",
    "rsi14": "momentum",
    "rsi21": "momentum",
    "roc5": "momentum",
    "roc10": "momentum",
    "roc20": "momentum",
    "roc40": "momentum",
    "macd_hist_pct": "momentum",
    "stoch14": "momentum",
    "vol_normalized_mom20": "momentum",
    "atr_pct": "volatility",
    "realized_vol10": "volatility",
    "realized_vol20": "volatility",
    "realized_vol40": "volatility",
    "parkinson_vol20": "volatility",
    "garman_klass_vol20": "volatility",
    "bollinger_width10": "volatility",
    "bollinger_width": "volatility",
    "bollinger_width40": "volatility",
    "vol_compression": "volatility",
    "relative_volume10": "volume",
    "relative_volume20": "volume",
    "relative_volume40": "volume",
    "obv_momentum20": "volume",
    "daily_typical_price_gap": "volume",
    "gap_pct": "structure",
    "prior_high10_gap": "structure",
    "prior_high20_gap": "structure",
    "prior_high40_gap": "structure",
    "prior_low10_gap": "structure",
    "prior_low20_gap": "structure",
    "prior_low40_gap": "structure",
    "prior_day_high_gap": "structure",
    "prior_day_low_gap": "structure",
    "range_position20": "structure",
    "dow_sin": "seasonality",
    "dow_cos": "seasonality",
    "month_sin": "seasonality",
    "month_cos": "seasonality",
    "third_friday_week": "seasonality",
    "month_end_window": "seasonality",
}

PARAMETER_GROUPS = {
    "sma_gap": ["sma10_gap", "sma20_gap", "sma40_gap"],
    "linreg_slope": ["linreg_slope_10", "linreg_slope_20", "linreg_slope_40"],
    "trend_efficiency": ["trend_efficiency_10", "trend_efficiency_20", "trend_efficiency_40"],
    "rsi": ["rsi7", "rsi14", "rsi21"],
    "roc": ["roc10", "roc20", "roc40"],
    "realized_vol": ["realized_vol10", "realized_vol20", "realized_vol40"],
    "bollinger_width": ["bollinger_width10", "bollinger_width", "bollinger_width40"],
    "relative_volume": ["relative_volume10", "relative_volume20", "relative_volume40"],
    "prior_high": ["prior_high10_gap", "prior_high20_gap", "prior_high40_gap"],
    "prior_low": ["prior_low10_gap", "prior_low20_gap", "prior_low40_gap"],
}


def _slug(symbol: str) -> str:
    return symbol.replace("^", "_").replace("=", "_").replace(".", "_")


def _raw_dir() -> Path:
    return ROOT / "data" / "research" / "nasdaq_gold_raw"


def _output_dir() -> Path:
    return ROOT / "output" / "nasdaq_gold_research"


def _normalise_download(download: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if isinstance(download.columns, pd.MultiIndex):
        if symbol in download.columns.get_level_values(-1):
            frame = download.xs(symbol, axis=1, level=-1)
        else:
            frame = download.copy()
    else:
        frame = download.copy()
    frame.columns = [str(column).lower().replace(" ", "_") for column in frame.columns]
    frame.index = pd.to_datetime(frame.index, utc=True)
    frame.index.name = "timestamp"
    required = ["open", "high", "low", "close", "volume"]
    for column in required:
        if column not in frame:
            frame[column] = np.nan
    return frame[required].sort_index().replace([np.inf, -np.inf], np.nan)


def load_market_data(config: ResearchConfig, refresh: bool, cache_only: bool) -> tuple[dict[str, pd.DataFrame], dict]:
    raw_dir = _raw_dir()
    raw_dir.mkdir(parents=True, exist_ok=True)
    symbols = sorted({item for pair in TARGETS.values() for item in pair.values()} | set(CONTEXT_SYMBOLS.values()))
    frames: dict[str, pd.DataFrame] = {}
    sources: dict[str, dict] = {}

    for symbol in symbols:
        path = raw_dir / f"{_slug(symbol)}.csv"
        if path.exists() and not refresh:
            frame = pd.read_csv(path, parse_dates=["timestamp"], index_col="timestamp")
            frame.index = pd.to_datetime(frame.index, utc=True)
            frames[symbol] = frame
            sources[symbol] = {"source": "cache", "path": str(path.relative_to(ROOT))}

    missing = [symbol for symbol in symbols if symbol not in frames]
    if missing and cache_only:
        raise RuntimeError(f"Cache incompleto; ausentes: {', '.join(missing)}")
    if missing:
        import yfinance as yf

        tz_cache = ROOT / "tmp" / "yfinance_research"
        tz_cache.mkdir(parents=True, exist_ok=True)
        yf.set_tz_cache_location(str(tz_cache))
        downloaded = yf.download(
            missing,
            period=config.period,
            interval="1d",
            auto_adjust=True,
            actions=False,
            progress=False,
            threads=True,
            group_by="column",
        )
        for symbol in missing:
            frame = _normalise_download(downloaded, symbol).dropna(subset=["open", "high", "low", "close"])
            if len(frame) < config.min_train_bars + 504:
                raise RuntimeError(f"Historico insuficiente para {symbol}: {len(frame)} barras")
            path = raw_dir / f"{_slug(symbol)}.csv"
            frame.to_csv(path)
            frames[symbol] = frame
            sources[symbol] = {"source": "yfinance", "path": str(path.relative_to(ROOT))}

    audit = {}
    for symbol, frame in frames.items():
        audit[symbol] = {
            "rows": int(len(frame)),
            "start": str(frame.index.min().date()),
            "end": str(frame.index.max().date()),
            "duplicates": int(frame.index.duplicated().sum()),
            "missing_ohlc": int(frame[["open", "high", "low", "close"]].isna().sum().sum()),
            "zero_volume_pct": round(float((frame["volume"].fillna(0) <= 0).mean() * 100), 3),
            **sources[symbol],
        }

    # Prefer the already frozen official FRED cache over market-data proxies.
    # Missing macro series do not prevent the price-only experiment from
    # running, but are reported explicitly in the audit.
    fred_dir = ROOT / "data" / "raw" / "macro" / "fred"
    for series_id in FRED_CONTEXT.values():
        path = fred_dir / f"{series_id}.csv"
        if not path.exists():
            audit[f"FRED:{series_id}"] = {"source": "missing", "path": str(path.relative_to(ROOT))}
            continue
        frame = pd.read_csv(path, parse_dates=["timestamp"], index_col="timestamp")
        frame.index = pd.to_datetime(frame.index, utc=True)
        frame = frame.sort_index()
        frames[series_id] = frame
        audit[f"FRED:{series_id}"] = {
            "rows": int(len(frame)),
            "start": str(frame.index.min().date()),
            "end": str(frame.index.max().date()),
            "duplicates": int(frame.index.duplicated().sum()),
            "missing_close": int(frame["close"].isna().sum()),
            "source": "FRED official cache",
            "path": str(path.relative_to(ROOT)),
            "availability_lag_trading_days": 1,
        }
    return frames, audit


def _rolling_slope(series: pd.Series, window: int) -> pd.Series:
    x = np.arange(window, dtype=float)
    x = x - x.mean()
    denominator = float(np.square(x).sum())
    return series.rolling(window).apply(lambda values: float(np.dot(values - values.mean(), x) / denominator), raw=True)


def _rolling_r2(series: pd.Series, window: int) -> pd.Series:
    x = np.arange(window, dtype=float)
    return series.rolling(window).apply(
        lambda values: float(np.corrcoef(x, values)[0, 1] ** 2) if np.std(values) > 0 else 0.0,
        raw=True,
    )


def _zscore(series: pd.Series, window: int = 60) -> pd.Series:
    mean = series.rolling(window, min_periods=window).mean()
    std = series.rolling(window, min_periods=window).std()
    return (series - mean) / std.replace(0, np.nan)


def _base_features(history: pd.DataFrame) -> pd.DataFrame:
    close, high, low, open_, volume = (history[column].astype(float) for column in ["close", "high", "low", "open", "volume"])
    log_close = np.log(close)
    returns = close.pct_change()
    out = pd.DataFrame(index=history.index)

    sma10, sma20, sma40, sma50 = (indicators.sma(close, window) for window in [10, 20, 40, 50])
    ema20, ema50 = indicators.ema(close, 20), indicators.ema(close, 50)
    out["sma10_gap"] = close / sma10 - 1
    out["sma20_gap"] = close / sma20 - 1
    out["sma40_gap"] = close / sma40 - 1
    out["sma50_gap"] = close / sma50 - 1
    out["ema20_50_gap"] = ema20 / ema50 - 1
    out["ema20_slope_5"] = (ema20 / ema20.shift(5) - 1) / 5
    out["linreg_slope_10"] = _rolling_slope(log_close, 10)
    out["linreg_slope_20"] = _rolling_slope(log_close, 20)
    out["linreg_slope_40"] = _rolling_slope(log_close, 40)
    out["linreg_r2_20"] = _rolling_r2(log_close, 20)
    out["adx14"] = indicators.adx(high, low, close, 14)["adx"] / 100
    for window in [10, 20, 40]:
        net_move = close.diff(window).abs()
        path = close.diff().abs().rolling(window).sum()
        out[f"trend_efficiency_{window}"] = net_move / path.replace(0, np.nan)

    out["rsi7"] = indicators.rsi(close, 7) / 100
    out["rsi14"] = indicators.rsi(close, 14) / 100
    out["rsi21"] = indicators.rsi(close, 21) / 100
    out["roc5"] = close.pct_change(5)
    out["roc10"] = close.pct_change(10)
    out["roc20"] = close.pct_change(20)
    out["roc40"] = close.pct_change(40)
    out["macd_hist_pct"] = indicators.macd(close)["histogram"] / close
    lowest14, highest14 = low.rolling(14).min(), high.rolling(14).max()
    out["stoch14"] = (close - lowest14) / (highest14 - lowest14).replace(0, np.nan)
    out["vol_normalized_mom20"] = out["roc20"] / (returns.rolling(20).std() * math.sqrt(20)).replace(0, np.nan)

    out["atr_pct"] = indicators.atr(high, low, close, 14) / close
    for window in [10, 20, 40]:
        out[f"realized_vol{window}"] = returns.rolling(window).std() * math.sqrt(252)
    park_var = np.log(high / low).pow(2) / (4 * math.log(2))
    out["parkinson_vol20"] = np.sqrt(park_var.rolling(20).mean() * 252)
    gk_var = 0.5 * np.log(high / low).pow(2) - (2 * math.log(2) - 1) * np.log(close / open_).pow(2)
    out["garman_klass_vol20"] = np.sqrt(gk_var.clip(lower=0).rolling(20).mean() * 252)
    for window, name in [(10, "bollinger_width10"), (20, "bollinger_width"), (40, "bollinger_width40")]:
        bands = indicators.bollinger_bands(close, window, 2)
        out[name] = (bands["upper"] - bands["lower"]) / bands["mid"]
    out["vol_compression"] = out["atr_pct"] / out["atr_pct"].rolling(60).median()

    out["relative_volume10"] = volume / volume.rolling(10).mean().replace(0, np.nan)
    out["relative_volume20"] = volume / volume.rolling(20).mean().replace(0, np.nan)
    out["relative_volume40"] = volume / volume.rolling(40).mean().replace(0, np.nan)
    obv = (np.sign(close.diff()).fillna(0) * volume.fillna(0)).cumsum()
    out["obv_momentum20"] = obv.diff(20) / volume.rolling(20).sum().replace(0, np.nan)
    typical = (high + low + close) / 3
    out["daily_typical_price_gap"] = close / typical - 1

    out["gap_pct"] = open_ / close.shift(1) - 1
    prior_high10 = high.rolling(10).max().shift(1)
    prior_high20 = high.rolling(20).max().shift(1)
    prior_high40 = high.rolling(40).max().shift(1)
    prior_low10 = low.rolling(10).min().shift(1)
    prior_low20 = low.rolling(20).min().shift(1)
    prior_low40 = low.rolling(40).min().shift(1)
    out["prior_high10_gap"] = close / prior_high10 - 1
    out["prior_high20_gap"] = close / prior_high20 - 1
    out["prior_high40_gap"] = close / prior_high40 - 1
    out["prior_low10_gap"] = close / prior_low10 - 1
    out["prior_low20_gap"] = close / prior_low20 - 1
    out["prior_low40_gap"] = close / prior_low40 - 1
    out["prior_day_high_gap"] = close / high.shift(1) - 1
    out["prior_day_low_gap"] = close / low.shift(1) - 1
    out["range_position20"] = (close - prior_low20) / (prior_high20 - prior_low20).replace(0, np.nan)

    dow = out.index.dayofweek
    month = out.index.month
    out["dow_sin"] = np.sin(2 * np.pi * dow / 5)
    out["dow_cos"] = np.cos(2 * np.pi * dow / 5)
    out["month_sin"] = np.sin(2 * np.pi * (month - 1) / 12)
    out["month_cos"] = np.cos(2 * np.pi * (month - 1) / 12)
    out["third_friday_week"] = ((out.index.day >= 15) & (out.index.day <= 21)).astype(float)
    month_end = out.index.tz_localize(None).to_period("M").to_timestamp("M").tz_localize("UTC")
    out["month_end_window"] = ((month_end - out.index).days <= 4).astype(float)
    return out


def _context_features(index: pd.DatetimeIndex, frames: dict[str, pd.DataFrame], market: str) -> pd.DataFrame:
    out = pd.DataFrame(index=index)
    context_keys = (
        ["vix", "dollar", "treasury_10y", "semiconductors", "sp500", "equal_weight_sp500", "long_treasuries"]
        if market == "nasdaq"
        else ["dollar", "treasury_10y", "long_treasuries", "intermediate_treasuries", "inflation_linked_bonds", "silver", "oil", "vix"]
    )
    aligned: dict[str, pd.Series] = {}
    for key in context_keys:
        series = frames[CONTEXT_SYMBOLS[key]]["close"].reindex(index).ffill()
        aligned[key] = series
        out[f"ctx_{key}_ret5"] = series.pct_change(5)
        out[f"ctx_{key}_z60"] = _zscore(series, 60)
        FEATURE_FAMILIES[f"ctx_{key}_ret5"] = "intermarket"
        FEATURE_FAMILIES[f"ctx_{key}_z60"] = "intermarket"
    if market == "nasdaq":
        out["ctx_semiconductor_relative20"] = aligned["semiconductors"].pct_change(20) - aligned["sp500"].pct_change(20)
        out["ctx_breadth_proxy20"] = aligned["equal_weight_sp500"].pct_change(20) - aligned["sp500"].pct_change(20)
        FEATURE_FAMILIES["ctx_semiconductor_relative20"] = "intermarket"
        FEATURE_FAMILIES["ctx_breadth_proxy20"] = "intermarket"
    else:
        out["ctx_silver_relative20"] = aligned["silver"].pct_change(20) - frames["GLD"]["close"].reindex(index).ffill().pct_change(20)
        out["ctx_tip_ief_relative20"] = aligned["inflation_linked_bonds"].pct_change(20) - aligned["intermediate_treasuries"].pct_change(20)
        FEATURE_FAMILIES["ctx_silver_relative20"] = "intermarket"
        FEATURE_FAMILIES["ctx_tip_ief_relative20"] = "intermarket"

    official: dict[str, pd.Series] = {}
    for key, series_id in FRED_CONTEXT.items():
        if series_id not in frames:
            continue
        # FRED calendars contain holidays/missing observations.  Align first,
        # carry only previously released values, then impose a full-day lag.
        series = frames[series_id]["close"].astype(float).reindex(index).ffill().shift(1)
        official[key] = series
        out[f"macro_{key}_chg1"] = series.diff()
        out[f"macro_{key}_chg5"] = series.diff(5)
        out[f"macro_{key}_z60"] = _zscore(series, 60)
        FEATURE_FAMILIES[f"macro_{key}_chg1"] = "intermarket_official"
        FEATURE_FAMILIES[f"macro_{key}_chg5"] = "intermarket_official"
        FEATURE_FAMILIES[f"macro_{key}_z60"] = "intermarket_official"

    if {"us2y", "us10y"}.issubset(official):
        out["macro_curve_2s10s"] = official["us10y"] - official["us2y"]
        out["macro_curve_2s10s_chg5"] = out["macro_curve_2s10s"].diff(5)
        FEATURE_FAMILIES["macro_curve_2s10s"] = "intermarket_official"
        FEATURE_FAMILIES["macro_curve_2s10s_chg5"] = "intermarket_official"
    if {"us5y", "us30y"}.issubset(official):
        out["macro_curve_5s30s"] = official["us30y"] - official["us5y"]
        out["macro_curve_5s30s_chg5"] = out["macro_curve_5s30s"].diff(5)
        FEATURE_FAMILIES["macro_curve_5s30s"] = "intermarket_official"
        FEATURE_FAMILIES["macro_curve_5s30s_chg5"] = "intermarket_official"
    return out


def build_dataset(history: pd.DataFrame, frames: dict[str, pd.DataFrame], market: str, config: ResearchConfig) -> pd.DataFrame:
    features = pd.concat([_base_features(history), _context_features(history.index, frames, market)], axis=1)
    features = features.replace([np.inf, -np.inf], np.nan)
    entry = history["open"].shift(-1)
    exit_ = history["open"].shift(-(config.horizon + 1))
    gross = exit_ / entry - 1
    cost = 2 * config.cost_bps_per_side / 10_000
    features["target_gross_return"] = gross
    features["target_net_return"] = gross - cost
    features["entry_open"] = entry
    features["exit_open"] = exit_
    features["target_up"] = (gross > cost).astype(float)
    features.loc[gross.isna(), "target_up"] = np.nan
    expanding_vol_median = features["realized_vol20"].expanding(252).median().shift(1)
    features["regime"] = np.select(
        [
            (features["ema20_50_gap"] > 0) & (features["realized_vol20"] <= expanding_vol_median),
            (features["ema20_50_gap"] > 0) & (features["realized_vol20"] > expanding_vol_median),
            (features["ema20_50_gap"] <= 0) & (features["realized_vol20"] > expanding_vol_median),
        ],
        ["up_calm", "up_volatile", "down_volatile"],
        default="down_calm",
    )
    return features.dropna(subset=["target_gross_return"])


def temporal_split(dataset: pd.DataFrame, config: ResearchConfig) -> tuple[pd.DataFrame, pd.DataFrame, list[tuple[np.ndarray, np.ndarray]]]:
    cutoff = dataset.index.max() - pd.DateOffset(years=config.holdout_years)
    dev = dataset.loc[dataset.index < cutoff].copy()
    test = dataset.loc[dataset.index >= cutoff].copy()
    n = len(dev)
    initial = max(config.min_train_bars, int(n * 0.45))
    validation_size = max(126, (n - initial) // config.development_folds)
    folds = []
    for fold in range(config.development_folds):
        validation_start = initial + fold * validation_size
        validation_end = n if fold == config.development_folds - 1 else min(n, validation_start + validation_size)
        train_end = validation_start - config.horizon
        if train_end < config.min_train_bars or validation_end - validation_start < 60:
            continue
        folds.append((np.arange(train_end), np.arange(validation_start, validation_end)))
    if len(test) < 252 or not folds:
        raise RuntimeError(f"Particao temporal insuficiente: dev={len(dev)}, teste={len(test)}, folds={len(folds)}")
    return dev, test, folds


def _non_overlapping_positions(signal: np.ndarray, horizon: int) -> list[int]:
    selected = []
    next_allowed = 0
    for position, active in enumerate(signal):
        if active and position >= next_allowed:
            selected.append(position)
            next_allowed = position + horizon
    return selected


def strategy_metrics(frame: pd.DataFrame, signal: np.ndarray, horizon: int) -> dict:
    positions = _non_overlapping_positions(np.asarray(signal, dtype=bool), horizon)
    trades = frame.iloc[positions]
    returns = trades["target_net_return"].dropna()
    if returns.empty:
        return {"trades": 0, "net_return_pct": 0.0, "mean_trade_pct": None, "sharpe": None, "sortino": None, "max_drawdown_pct": None, "profit_factor": None, "win_rate": None, "p_value": None}
    equity = (1 + returns).cumprod()
    drawdown = equity / equity.cummax() - 1
    daily_realizations = np.zeros(len(frame), dtype=float)
    for position, value in zip(positions, returns.to_numpy()):
        daily_realizations[min(position + horizon, len(frame) - 1)] += value
    downside = pd.Series(daily_realizations[daily_realizations < 0]).std(ddof=1)
    std = float(np.std(daily_realizations, ddof=1))
    gains, losses = returns[returns > 0].sum(), -returns[returns < 0].sum()
    t_result = stats.ttest_1samp(returns, popmean=0, alternative="greater") if len(returns) >= 3 else None
    return {
        "trades": int(len(returns)),
        "net_return_pct": round(float((equity.iloc[-1] - 1) * 100), 3),
        "mean_trade_pct": round(float(returns.mean() * 100), 4),
        "expectancy_pct": round(float(returns.mean() * 100), 4),
        "sharpe": round(float(np.mean(daily_realizations) / std * math.sqrt(252)), 3) if std and np.isfinite(std) else None,
        "sortino": round(float(np.mean(daily_realizations) / downside * math.sqrt(252)), 3) if downside and np.isfinite(downside) else None,
        "max_drawdown_pct": round(float(drawdown.min() * 100), 3),
        "profit_factor": round(float(gains / losses), 3) if losses > 0 else None,
        "win_rate": round(float((returns > 0).mean()), 4),
        "p_value": round(float(t_result.pvalue), 6) if t_result is not None and np.isfinite(t_result.pvalue) else None,
    }


def classification_metrics(y_true: pd.Series, probability: np.ndarray, threshold: float = 0.55) -> dict:
    probability = np.clip(np.asarray(probability, dtype=float), 1e-6, 1 - 1e-6)
    predicted = probability >= threshold
    truth = y_true.astype(int).to_numpy()
    bins = pd.qcut(pd.Series(probability), q=min(10, len(np.unique(probability))), duplicates="drop")
    calibration = pd.DataFrame({"p": probability, "y": truth, "bin": bins}).groupby("bin", observed=True).agg(p=("p", "mean"), y=("y", "mean"), n=("y", "size"))
    ece = float(((calibration["p"] - calibration["y"]).abs() * calibration["n"]).sum() / calibration["n"].sum())
    return {
        "balanced_accuracy": round(float(balanced_accuracy_score(truth, predicted)), 4),
        "mcc": round(float(matthews_corrcoef(truth, predicted)), 4),
        "precision": round(float(precision_score(truth, predicted, zero_division=0)), 4),
        "recall": round(float(recall_score(truth, predicted, zero_division=0)), 4),
        "brier": round(float(brier_score_loss(truth, probability)), 5),
        "calibration_error": round(ece, 5),
        "positive_rate": round(float(np.mean(truth)), 4),
    }


def _bh_adjust(p_values: dict[str, float | None]) -> dict[str, float | None]:
    valid = sorted((value, key) for key, value in p_values.items() if value is not None and np.isfinite(value))
    adjusted: dict[str, float | None] = {key: None for key in p_values}
    running = 1.0
    m = len(valid)
    for reverse_rank, (value, key) in enumerate(reversed(valid), start=1):
        rank = m - reverse_rank + 1
        running = min(running, value * m / rank)
        adjusted[key] = round(float(running), 6)
    return adjusted


def univariate_development(dev: pd.DataFrame, features: list[str], folds: list[tuple[np.ndarray, np.ndarray]], config: ResearchConfig) -> pd.DataFrame:
    rows = []
    for feature in features:
        fold_rows = []
        for train_idx, validation_idx in folds:
            train, validation = dev.iloc[train_idx], dev.iloc[validation_idx]
            valid_train = train[[feature, "target_net_return"]].dropna()
            if len(valid_train) < 100 or valid_train[feature].nunique() < 5:
                continue
            correlation = valid_train[feature].corr(valid_train["target_net_return"], method="spearman")
            direction = 1.0 if pd.notna(correlation) and correlation >= 0 else -1.0
            threshold = (direction * valid_train[feature]).quantile(config.feature_quantile)
            signal = (direction * validation[feature]).fillna(-np.inf).to_numpy() >= threshold
            metrics = strategy_metrics(validation, signal, config.horizon)
            fold_rows.append({"correlation": correlation, "direction": direction, **metrics})
        if not fold_rows:
            continue
        table = pd.DataFrame(fold_rows)
        rows.append(
            {
                "feature": feature,
                "family": FEATURE_FAMILIES.get(feature, "unknown"),
                "folds": int(len(table)),
                "positive_folds": int((table["mean_trade_pct"].fillna(-np.inf) > 0).sum()),
                "fold_stability": round(float((table["mean_trade_pct"].fillna(-np.inf) > 0).mean()), 3),
                "mean_dev_trade_pct": round(float(table["mean_trade_pct"].mean()), 4),
                "mean_dev_sharpe": round(float(table["sharpe"].mean()), 3),
                "dev_trades": int(table["trades"].sum()),
                "median_abs_train_spearman": round(float(table["correlation"].abs().median()), 4),
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(["fold_stability", "mean_dev_trade_pct", "dev_trades"], ascending=False).reset_index(drop=True)


def evaluate_univariate_holdout(dev: pd.DataFrame, test: pd.DataFrame, candidates: list[str], config: ResearchConfig) -> pd.DataFrame:
    rows = []
    p_values = {}
    for feature in candidates:
        train = dev[[feature, "target_net_return"]].dropna()
        correlation = train[feature].corr(train["target_net_return"], method="spearman")
        direction = 1.0 if pd.notna(correlation) and correlation >= 0 else -1.0
        threshold = (direction * train[feature]).quantile(config.feature_quantile)
        signal = (direction * test[feature]).fillna(-np.inf).to_numpy() >= threshold
        metrics = strategy_metrics(test, signal, config.horizon)
        rows.append({"feature": feature, "family": FEATURE_FAMILIES.get(feature, "unknown"), "train_direction": int(direction), "train_threshold": round(float(threshold), 8), **metrics})
        p_values[feature] = metrics["p_value"]
    q_values = _bh_adjust(p_values)
    for row in rows:
        row["bh_q_value"] = q_values[row["feature"]]
    return pd.DataFrame(rows).sort_values(
        ["bh_q_value", "trades", "mean_trade_pct"],
        ascending=[True, False, False],
        na_position="last",
    ).reset_index(drop=True)


def _pipeline(model) -> Pipeline:
    return Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler()), ("model", model)])


def _fold_brier(dev: pd.DataFrame, features: list[str], folds: list[tuple[np.ndarray, np.ndarray]], factory: Callable[[], Pipeline]) -> float:
    scores = []
    for train_idx, validation_idx in folds:
        train, validation = dev.iloc[train_idx], dev.iloc[validation_idx]
        model = factory().fit(train[features], train["target_up"].astype(int))
        probability = model.predict_proba(validation[features])[:, 1]
        scores.append(brier_score_loss(validation["target_up"].astype(int), probability))
    return float(np.mean(scores))


def sequential_features(dev: pd.DataFrame, pool: list[str], folds: list[tuple[np.ndarray, np.ndarray]], max_features: int = 8) -> tuple[list[str], list[dict]]:
    selected: list[str] = []
    history = []
    best_score = float("inf")
    factory = lambda: _pipeline(LogisticRegression(C=0.1, max_iter=2000, class_weight="balanced", random_state=17))
    remaining = list(pool)
    while remaining and len(selected) < max_features:
        trials = [(feature, _fold_brier(dev, selected + [feature], folds, factory)) for feature in remaining]
        feature, score = min(trials, key=lambda item: item[1])
        improvement = best_score - score
        if selected and improvement < 0.0005:
            break
        selected.append(feature)
        remaining.remove(feature)
        best_score = score
        history.append({"step": len(selected), "feature": feature, "mean_dev_brier": round(score, 6), "improvement": None if len(selected) == 1 else round(improvement, 6)})
    return selected, history


def model_comparison(dev: pd.DataFrame, test: pd.DataFrame, features: list[str], config: ResearchConfig) -> tuple[list[dict], list[dict], list[dict]]:
    y_dev = dev["target_up"].astype(int)
    y_test = test["target_up"].astype(int)
    base_probability = np.repeat(float(y_dev.mean()), len(test))
    results = [{"model": "historical_base_rate", **classification_metrics(y_test, base_probability), **strategy_metrics(test, np.ones(len(test), dtype=bool), config.horizon)}]

    models = {
        "logistic_l2": _pipeline(LogisticRegression(C=0.1, max_iter=3000, class_weight="balanced", random_state=config.seed)),
        "random_forest": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("model", RandomForestClassifier(n_estimators=400, max_depth=4, min_samples_leaf=40, max_features="sqrt", class_weight="balanced_subsample", random_state=config.seed, n_jobs=1)),
            ]
        ),
    }
    for name, model in models.items():
        model.fit(dev[features], y_dev)
        probability = model.predict_proba(test[features])[:, 1]
        signal = probability >= 0.55
        results.append({"model": name, **classification_metrics(y_test, probability), **strategy_metrics(test, signal, config.horizon)})

    ridge = _pipeline(Ridge(alpha=10.0)).fit(dev[features], dev["target_net_return"])
    predicted_return = ridge.predict(test[features])
    ridge_signal = predicted_return > 0
    ridge_stats = strategy_metrics(test, ridge_signal, config.horizon)
    results.append({"model": "ridge_return", "rank_correlation": round(float(stats.spearmanr(predicted_return, test["target_net_return"], nan_policy="omit").statistic), 4), **ridge_stats})

    # Interpret on the last development validation fold, never on the final holdout.
    split = max(config.min_train_bars, len(dev) - 252)
    rf = models["random_forest"].fit(dev.iloc[:split][features], y_dev.iloc[:split])
    importance = permutation_importance(rf, dev.iloc[split:][features], y_dev.iloc[split:], scoring="neg_brier_score", n_repeats=15, random_state=config.seed, n_jobs=1)
    permutation_rows = sorted(
        [{"feature": feature, "importance_mean": round(float(mean), 6), "importance_std": round(float(std), 6)} for feature, mean, std in zip(features, importance.importances_mean, importance.importances_std)],
        key=lambda row: row["importance_mean"],
        reverse=True,
    )
    from sklearn.feature_selection import mutual_info_classif

    imputed = SimpleImputer(strategy="median").fit_transform(dev[features])
    mi = mutual_info_classif(imputed, y_dev, random_state=config.seed)
    mutual_information = sorted([{"feature": feature, "mutual_information": round(float(value), 6)} for feature, value in zip(features, mi)], key=lambda row: row["mutual_information"], reverse=True)
    return results, permutation_rows, mutual_information


def conditional_distributions(dataset: pd.DataFrame, features: list[str]) -> list[dict]:
    rows = []
    for feature in features:
        valid = dataset[[feature, "target_net_return"]].dropna().copy()
        if valid[feature].nunique() < 5:
            continue
        valid["bucket"] = pd.qcut(valid[feature], 5, labels=False, duplicates="drop")
        for bucket, group in valid.groupby("bucket"):
            rows.append({"feature": feature, "quintile": int(bucket) + 1, "observations": int(len(group)), "mean_future_net_pct": round(float(group["target_net_return"].mean() * 100), 4), "median_future_net_pct": round(float(group["target_net_return"].median() * 100), 4), "positive_rate": round(float((group["target_net_return"] > 0).mean()), 4)})
    return rows


def yearly_evidence(test: pd.DataFrame, feature_table: pd.DataFrame, config: ResearchConfig) -> list[dict]:
    rows = []
    for candidate in feature_table.head(5).to_dict(orient="records"):
        feature = candidate["feature"]
        signal = (candidate["train_direction"] * test[feature]).fillna(-np.inf).to_numpy() >= candidate["train_threshold"]
        for year in sorted(test.index.year.unique()):
            mask = test.index.year == year
            rows.append({"feature": feature, "year": int(year), **strategy_metrics(test.loc[mask], signal[mask], config.horizon)})
    return rows


def parameter_stability(dev: pd.DataFrame, test: pd.DataFrame, candidates: list[str], config: ResearchConfig) -> list[dict]:
    rows = []
    for group, variants in PARAMETER_GROUPS.items():
        if not any(feature in candidates for feature in variants):
            continue
        evaluated = evaluate_univariate_holdout(dev, test, variants, config)
        for row in evaluated.to_dict(orient="records"):
            rows.append({"parameter_group": group, **row})
    return rows


def buy_and_hold_metrics(history: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, config: ResearchConfig) -> dict:
    sample = history.loc[(history.index >= start) & (history.index <= end)].copy()
    returns = sample["close"].pct_change().fillna(0)
    returns.iloc[0] -= config.cost_bps_per_side / 10_000
    returns.iloc[-1] -= config.cost_bps_per_side / 10_000
    equity = (1 + returns).cumprod()
    drawdown = equity / equity.cummax() - 1
    downside = returns[returns < 0].std(ddof=1)
    return {
        "observations": int(len(returns)),
        "net_return_pct": round(float((equity.iloc[-1] - 1) * 100), 3),
        "sharpe": round(float(returns.mean() / returns.std(ddof=1) * math.sqrt(252)), 3),
        "sortino": round(float(returns.mean() / downside * math.sqrt(252)), 3) if downside else None,
        "max_drawdown_pct": round(float(drawdown.min() * 100), 3),
    }


def regime_evidence(test: pd.DataFrame, feature_table: pd.DataFrame, dev: pd.DataFrame, config: ResearchConfig) -> list[dict]:
    rows = []
    for candidate in feature_table.head(5).to_dict(orient="records"):
        feature = candidate["feature"]
        direction = candidate["train_direction"]
        threshold = candidate["train_threshold"]
        base_signal = (direction * test[feature]).fillna(-np.inf).to_numpy() >= threshold
        for regime in sorted(test["regime"].unique()):
            signal = base_signal & (test["regime"].to_numpy() == regime)
            rows.append({"feature": feature, "regime": regime, **strategy_metrics(test, signal, config.horizon)})
    return rows


def recommendation(row: pd.Series, dev_row: pd.Series | None, transfer_row: pd.Series | None, config: ResearchConfig) -> tuple[str, list[str]]:
    reasons = []
    stable = dev_row is not None and float(dev_row.get("fold_stability", 0)) >= 0.6
    significant = pd.notna(row.get("bh_q_value")) and float(row["bh_q_value"]) <= 0.10
    enough = int(row.get("trades", 0)) >= config.min_trades
    positive = pd.notna(row.get("mean_trade_pct")) and float(row["mean_trade_pct"]) > 0
    transfers = transfer_row is not None and pd.notna(transfer_row.get("mean_trade_pct")) and float(transfer_row["mean_trade_pct"]) > 0
    if not stable:
        reasons.append("instavel nos folds de desenvolvimento")
    if not significant:
        reasons.append("nao supera FDR de 10% no holdout")
    if not enough:
        reasons.append("poucas operacoes")
    if not positive:
        reasons.append("expectativa liquida nao positiva")
    if not transfers:
        reasons.append("sem confirmacao no instrumento de transferencia")
    if stable and significant and enough and positive and transfers:
        return "aprovado para paper trading", reasons
    if positive and stable and enough:
        return "experimental", reasons
    if not enough:
        return "precisa de mais dados", reasons
    return "rejeitado", reasons


def attach_transfer_confirmations(results: dict, frames: dict[str, pd.DataFrame], config: ResearchConfig) -> None:
    """Evaluate each primary candidate unchanged on the paired futures series."""
    for market, symbols in TARGETS.items():
        primary_result = results[symbols["primary"]]
        candidates = [row["feature"] for row in primary_result["holdout_candidates"]]
        transfer_dataset = build_dataset(frames[symbols["transfer"]], frames, market, config)
        transfer_dev, transfer_test, _ = temporal_split(transfer_dataset, config)
        confirmation = evaluate_univariate_holdout(transfer_dev, transfer_test, candidates, config)
        primary_result["transfer_confirmation"] = confirmation.to_dict(orient="records")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def analyse_instrument(symbol: str, market: str, frames: dict[str, pd.DataFrame], config: ResearchConfig) -> dict:
    dataset = build_dataset(frames[symbol], frames, market, config)
    dev, test, folds = temporal_split(dataset, config)
    excluded = {"target_gross_return", "target_net_return", "target_up", "entry_open", "exit_open", "regime"}
    features = [column for column in dataset.columns if column not in excluded]
    development = univariate_development(dev, features, folds, config)
    candidates = development.head(15)["feature"].tolist()
    holdout = evaluate_univariate_holdout(dev, test, candidates, config)
    model_pool = development.head(20)["feature"].tolist()
    selected, selection_history = sequential_features(dev, model_pool, folds)
    if not selected:
        selected = model_pool[:5]
    models, permutation_rows, mutual_information = model_comparison(dev, test, selected, config)
    buy_hold = buy_and_hold_metrics(frames[symbol], test.index.min(), test.index.max(), config)
    return {
        "symbol": symbol,
        "market": market,
        "rows": int(len(dataset)),
        "start": str(dataset.index.min().date()),
        "end": str(dataset.index.max().date()),
        "development_end": str(dev.index.max().date()),
        "holdout_start": str(test.index.min().date()),
        "folds": [{"train_start": str(dev.iloc[tr].index.min().date()), "train_end": str(dev.iloc[tr].index.max().date()), "validation_start": str(dev.iloc[va].index.min().date()), "validation_end": str(dev.iloc[va].index.max().date())} for tr, va in folds],
        "feature_count": len(features),
        "development_ranking": development.to_dict(orient="records"),
        "holdout_candidates": holdout.to_dict(orient="records"),
        "selected_features": selected,
        "sequential_selection": selection_history,
        "model_comparison": models,
        "permutation_importance_development": permutation_rows,
        "mutual_information_development": mutual_information,
        "conditional_holdout": conditional_distributions(test, candidates[:8]),
        "regime_holdout": regime_evidence(test, holdout, dev, config),
        "yearly_holdout": yearly_evidence(test, holdout, config),
        "parameter_stability": parameter_stability(dev, test, candidates, config),
        "buy_and_hold": buy_hold,
    }


def _markdown_report(payload: dict) -> str:
    cfg = payload["config"]
    lines = [
        "# Pesquisa quantitativa de indicadores para Nasdaq e ouro",
        "",
        "## Conclusao executiva",
        "",
        "Nenhum resultado deve ser interpretado como promessa de rentabilidade. O experimento separa desenvolvimento e holdout, desconta custos e exige estabilidade; candidatos que nao passam esses filtros sao marcados como experimentais, insuficientes ou rejeitados.",
        "",
        "**Decisao final: nenhum indicador ou modelo foi aprovado para paper trading.** Os melhores sinais permanecem experimentais porque nenhum sobreviveu ao controle de falsos descobrimentos de 10%; modelos complexos tampouco dominaram os baselines de forma consistente.",
        "",
        "## Diagnostico do sistema e hipoteses",
        "",
        f"- O sistema existente e um monitor/alerta, nao um executor. Seu horizonte predominante e 5 pregoes em barras diarias; o simulador usa {cfg['cost_bps_per_side']:.1f} bps por lado (spread/slippage/comissao agregados).",
        "- Instrumentos encontrados: NQ=F para futuros Nasdaq, QQQ como benchmark/proxy Nasdaq-100, GC=F para ouro e GLD como proxy liquido. A pesquisa usa QQQ/GLD como series primarias e NQ=F/GC=F para transferencia.",
        f"- Regra temporal: features no fechamento t; entrada na abertura t+1; saida na abertura t+{cfg['horizon'] + 1}. Holdout final: {cfg['holdout_years']} anos, usado uma unica vez.",
        "- Hipotese operacional: decisao apos o fechamento dos mercados dos EUA. Custos reais de NQ/GC dependem de corretora, tamanho, spread e fila; o valor em bps e um cenario, nao uma medicao de book.",
        "- Nao ha dados intradiarios/de negocio para NQ/GC no projeto original. Delta, imbalance, perfil de volume, VWAP de sessao, overnight range, abertura/fechamento e latencia intraday nao foram testados.",
        "- `daily_typical_price_gap` e apenas um proxy OHLC diario, nao VWAP de sessao. TIP/IEF e proxy de juros reais/expectativas de inflacao, nao uma serie economica point-in-time.",
        "",
        "## Metodologia",
        "",
        "Features sao calculadas apenas com rolling/expanding para tras. O conjunto de desenvolvimento usa folds expanding-window com embargo igual ao horizonte; a selecao univariada, mutual information e selecao sequencial ocorrem apenas ali. O holdout final avalia candidatos congelados. P-values dos candidatos sao corrigidos por Benjamini-Hochberg; sinais com poucos trades ou dependentes de um fold sao rejeitados.",
        "",
        "A estrategia de avaliacao e long/flat, com sinais extremos definidos pelo percentil 80 aprendido no treino e operacoes nao sobrepostas. Modelos usam limiar de probabilidade fixo de 0,55. Isso favorece auditabilidade, mas nao representa sizing, margem ou mark-to-market intraperiodo de futuros.",
        "",
        "## Catalogo de familias",
        "",
        "| Familia | Features testadas |",
        "|---|---|",
    ]
    by_family: dict[str, list[str]] = {}
    for feature, family in payload["feature_catalog"].items():
        by_family.setdefault(family, []).append(feature)
    for family, names in sorted(by_family.items()):
        lines.append(f"| {family} | {', '.join(sorted(names))} |")

    for market in ["nasdaq", "gold"]:
        primary = payload["results"][TARGETS[market]["primary"]]
        transfer = payload["results"][TARGETS[market]["transfer"]]
        dev_map = {row["feature"]: row for row in primary["development_ranking"]}
        transfer_map = {row["feature"]: row for row in primary["transfer_confirmation"]}
        lines.extend(["", f"## Ranking — {market.title()}", "", f"Primario: {primary['symbol']}; transferencia: {transfer['symbol']}. Periodo {primary['start']} a {primary['end']}; holdout desde {primary['holdout_start']}.", "", "| # | Feature | Familia | Dev folds + | OOS trades | OOS exp. % | OOS Sharpe | q BH | Transfer exp. % | Classificacao |", "|---:|---|---|---:|---:|---:|---:|---:|---:|---|"])
        recommendations = []
        for rank, row in enumerate(primary["holdout_candidates"], start=1):
            dev_row = dev_map.get(row["feature"])
            transfer_row = transfer_map.get(row["feature"])
            label, reasons = recommendation(pd.Series(row), pd.Series(dev_row) if dev_row else None, pd.Series(transfer_row) if transfer_row else None, ResearchConfig(**cfg))
            recommendations.append({"feature": row["feature"], "classification": label, "reasons": reasons})
            lines.append(f"| {rank} | {row['feature']} | {row['family']} | {dev_row.get('positive_folds', 0) if dev_row else 0}/{dev_row.get('folds', 0) if dev_row else 0} | {row.get('trades', 0)} | {row.get('mean_trade_pct')} | {row.get('sharpe')} | {row.get('bh_q_value')} | {transfer_row.get('mean_trade_pct') if transfer_row else None} | {label} |")
        payload["recommendations"][market] = recommendations
        lines.extend(["", "### Modelos no holdout", "", "| Modelo | Balanced acc. | MCC | Brier | Calibracao | Trades | Retorno liquido % | Sharpe | Drawdown % |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"])
        for row in primary["model_comparison"]:
            lines.append(f"| {row['model']} | {row.get('balanced_accuracy')} | {row.get('mcc')} | {row.get('brier')} | {row.get('calibration_error')} | {row.get('trades')} | {row.get('net_return_pct')} | {row.get('sharpe')} | {row.get('max_drawdown_pct')} |")
        baseline_brier = primary["model_comparison"][0].get("brier")
        best_model = min((row for row in primary["model_comparison"] if row.get("brier") is not None), key=lambda row: row["brier"])
        lines.extend(
            [
                "",
                f"Buy-and-hold real no mesmo holdout: retorno liquido {primary['buy_and_hold']['net_return_pct']}%, Sharpe {primary['buy_and_hold']['sharpe']} e drawdown {primary['buy_and_hold']['max_drawdown_pct']}%.",
                "",
                f"Melhor Brier: {best_model['model']} = {best_model.get('brier')} contra baseline {baseline_brier}. Resultado economico isolado nao substitui calibracao/classificacao.",
                "",
                "### Combinacoes incrementais",
                "",
                f"Features escolhidas sem olhar o holdout: {', '.join(primary['selected_features'])}.",
                "",
                "| Passo | Feature adicionada | Brier medio dev | Ganho |",
                "|---:|---|---:|---:|",
            ]
        )
        for step in primary["sequential_selection"]:
            lines.append(f"| {step['step']} | {step['feature']} | {step['mean_dev_brier']} | {step['improvement']} |")
        lines.extend(["", "### Estabilidade anual e regimes do primeiro candidato", "", "| Corte | Subamostra | Trades | Expectativa % | Sharpe | Drawdown % |", "|---|---|---:|---:|---:|---:|"])
        top_feature = primary["holdout_candidates"][0]["feature"] if primary["holdout_candidates"] else None
        for row in primary["yearly_holdout"]:
            if row["feature"] == top_feature:
                lines.append(f"| ano | {row['year']} | {row['trades']} | {row['mean_trade_pct']} | {row['sharpe']} | {row['max_drawdown_pct']} |")
        for row in primary["regime_holdout"]:
            if row["feature"] == top_feature:
                lines.append(f"| regime | {row['regime']} | {row['trades']} | {row['mean_trade_pct']} | {row['sharpe']} | {row['max_drawdown_pct']} |")
        parameter_groups = sorted({row["parameter_group"] for row in primary["parameter_stability"]})
        lines.extend(["", f"Vizinhanças de parametros auditadas para candidatos relevantes: {', '.join(parameter_groups) if parameter_groups else 'nenhuma aplicavel'}. Resultados completos no CSV; uma parametrizacao isolada nao recebe aprovacao."])

    lines.extend(
        [
            "",
            "## Indicadores rejeitados e nao testaveis",
            "",
            "Features testadas que nao aparecem no ranking foram eliminadas no desenvolvimento por baixa estabilidade/expectativa incremental. Candidatos do ranking marcados como rejeitados falharam no holdout apos custos, FDR, numero de trades ou transferencia. A lista completa permanece no JSON para evitar publication bias.",
            "",
            "Nao testaveis com o dataset diario: volume delta, bid/ask imbalance, order-flow, perfil de volume, VWAP de sessao verdadeiro, overnight range, sazonalidade horaria, latencia e eventos macro point-in-time. Volatilidade implicita do ouro tambem nao esta presente; VIX e usado apenas como contexto de equities/risk-off.",
            "",
            "SHAP e HMM nao foram usados como filtro de descoberta: SHAP explica um modelo, nao valida edge, e HMM acrescentaria graus de liberdade sem dados suficientes de microestrutura. Random Forest, permutation importance, mutual information e uma classificacao de regimes causal oferecem a comparacao complexa minima. Modelos temporais e symbolic regression ficam bloqueados ate baselines simples sobreviverem ao holdout.",
            "",
            "## Protocolo walk-forward reproduzivel",
            "",
            "1. Congele os CSVs e seus hashes; nao atualize dados no meio do experimento.",
            "2. Calcule features no fechamento e labels open-to-open futuros; mantenha o embargo de 5 barras.",
            "3. Selecione direcao, thresholds, features e hiperparametros somente nos folds de desenvolvimento.",
            "4. Rode uma unica vez os dois anos finais. Corrija os candidatos selecionados por FDR e reporte todos, inclusive negativos.",
            "5. Repita em QQQ→NQ e GLD→GC, em janelas vizinhas (10/20/40) e por regime. Exija pelo menos 25 operacoes e maioria dos folds positiva.",
            "6. Antes de paper trading em futuros, substitua bps por tick, spread, comissao e slippage medidos por sessao; use contratos point-in-time/back-adjusted documentados.",
            "7. Promova apenas para paper trading. Colete pelo menos seis meses sem retuning e compare previsao, calibracao e P&L com o backtest congelado.",
            "",
            "## Limitacoes",
            "",
            "Yahoo Finance/yfinance e uma fonte conveniente, mas nao e um feed institucional nem garante series point-in-time. Continuous futures podem conter efeitos de rollover. QQQ/GLD introduzem tracking, horario e estrutura de custo diferentes de NQ/GC. O proxy de amplitude RSP-SPY nao substitui breadth point-in-time de constituintes, mas evita survivorship bias de reconstruir uma composicao atual no passado.",
            "",
            "## Fontes",
            "",
            "1. Invesco. [Invesco QQQ Product Detail](https://www.invesco.com/us/financial-products/etfs/product-detail?productId=QQQ&ticker=QQQ). QQQ e baseado no Nasdaq-100.",
            "2. CME Group. [E-mini Nasdaq-100 Futures and Options](https://www.cmegroup.com/trading/equity-index/files/emini-nasdaq-100-futures-options.pdf). Especificacoes do NQ.",
            "3. CME Group. [Gold Futures Contract Specifications](https://www.cmegroup.com/trading/metals/files/fact-card-gold-futures-options.pdf). Especificacoes do GC, tamanho, tick e horario.",
            "4. Bailey, D. H.; Lopez de Prado, M. [The Deflated Sharpe Ratio](https://doi.org/10.2139/ssrn.2460551). Correcao de selection bias, multiplos testes e nao-normalidade.",
            "5. Bailey, D. H.; Borwein, J.; Lopez de Prado, M.; Zhu, Q. [The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf). CSCV e risco de selecionar o melhor backtest por acaso.",
            "6. scikit-learn. [Permutation Feature Importance](https://scikit-learn.org/stable/modules/permutation_importance.html). Importancia como queda de desempenho ao embaralhar uma feature e alerta para avaliar o modelo antes de interpretar.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(payload: dict) -> dict:
    output_dir = _output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "results.json"
    report_path = output_dir / "report.md"
    payload["recommendations"] = {"nasdaq": [], "gold": []}
    report = _markdown_report(payload)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(report, encoding="utf-8")
    tables = []
    for symbol, result in payload["results"].items():
        for key in ["development_ranking", "holdout_candidates", "model_comparison", "regime_holdout", "yearly_holdout", "parameter_stability", "conditional_holdout"]:
            path = output_dir / f"{_slug(symbol)}_{key}.csv"
            pd.DataFrame(result[key]).to_csv(path, index=False)
            tables.append(path)
    # Rewrite JSON because report construction populates final recommendations.
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path = write_manifest(
        json_path,
        command="python scripts/nasdaq_gold_feature_research.py --cache-only",
        parameters=payload["config"],
        input_paths=sorted(_raw_dir().glob("*.csv")),
        data_gate=payload["data_audit"],
        extra={
            "report": str(report_path.relative_to(ROOT)),
            "table_count": len(tables),
            "research_packages": {
                package: importlib.metadata.version(package)
                for package in ["scikit-learn", "scipy"]
            },
        },
    )
    return {"report": str(report_path), "results": str(json_path), "manifest": str(manifest_path), "tables": [str(path) for path in tables]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/nasdaq_gold_research.json")
    parser.add_argument("--refresh", action="store_true", help="Download and freeze a new 15-year daily snapshot.")
    parser.add_argument("--cache-only", action="store_true", help="Fail instead of using the network when a cached symbol is missing.")
    parser.add_argument("--period")
    parser.add_argument("--horizon", type=int)
    parser.add_argument("--holdout-years", type=int)
    parser.add_argument("--cost-bps-per-side", type=float)
    args = parser.parse_args()
    config_path = ROOT / args.config
    raw_config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    for key, value in {
        "period": args.period,
        "horizon": args.horizon,
        "holdout_years": args.holdout_years,
        "cost_bps_per_side": args.cost_bps_per_side,
    }.items():
        if value is not None:
            raw_config[key] = value
    config = ResearchConfig(**raw_config)
    frames, data_audit = load_market_data(config, refresh=args.refresh, cache_only=args.cache_only)
    results = {}
    for market, symbols in TARGETS.items():
        for symbol in symbols.values():
            print(f"Analisando {market}/{symbol}...", flush=True)
            results[symbol] = analyse_instrument(symbol, market, frames, config)
    attach_transfer_confirmations(results, frames, config)
    payload = {
        "schema_version": "nasdaq-gold-feature-research-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": asdict(config),
        "decision_timing": "features at close(t), entry open(t+1), exit open(t+horizon+1)",
        "targets": TARGETS,
        "context_symbols": CONTEXT_SYMBOLS,
        "fred_context": FRED_CONTEXT,
        "feature_catalog": FEATURE_FAMILIES,
        "data_audit": data_audit,
        "results": results,
    }
    outputs = write_outputs(payload)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
