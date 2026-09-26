"""Discover and test complete long/short trading setups without leakage.

Signals are observed after close(t). Orders enter at open(t+1). Stops and
targets are fixed from ATR known at t; if both touch in one daily candle the
simulator assumes the stop happened first. Time exits occur at the open after
the configured number of complete holding bars. All costs are charged twice.

Rule parameters and ML probability thresholds are selected on expanding
development folds. The final two-year holdout is evaluated once, unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import mutual_info_classif
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, brier_score_loss, matthews_corrcoef, precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import indicators  # noqa: E402
from app.research_provenance import write_manifest  # noqa: E402
from scripts.nasdaq_gold_feature_research import (  # noqa: E402
    CONTEXT_SYMBOLS,
    TARGETS,
    ResearchConfig,
    _bh_adjust,
    build_dataset,
    buy_and_hold_metrics,
    load_market_data,
    temporal_split,
)


@dataclass(frozen=True)
class OperationalConfig:
    period: str = "15y"
    horizon: int = 5
    holdout_years: int = 2
    development_folds: int = 5
    cost_bps_per_side: float = 7.0
    min_train_bars: int = 756
    min_trades: int = 30
    seed: int = 20260911
    final_candidates: int = 20
    max_per_family_side: int = 3


SIDE_MODES = ("long", "short", "both")
STOP_ATR = (1.0, 1.5, 2.0)
TARGET_ATR = (1.5, 2.0, 3.0)
MAX_HOLD = (3, 5, 10)


def _output_dir() -> Path:
    return ROOT / "output" / "operational_setup_research"


def _stable_id(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha1(encoded).hexdigest()[:12]


def indicator_state(history: pd.DataFrame) -> pd.DataFrame:
    close, high, low = (history[column].astype(float) for column in ["close", "high", "low"])
    out = pd.DataFrame(index=history.index)
    for window in [10, 20, 40, 50, 100, 200]:
        out[f"sma{window}"] = close.rolling(window).mean()
    for window in [7, 14, 21]:
        out[f"rsi{window}"] = indicators.rsi(close, window)
    out["adx14"] = indicators.adx(high, low, close, 14)["adx"]
    out["atr14"] = indicators.atr(high, low, close, 14)
    out["ema20"] = indicators.ema(close, 20)
    out["ema20_slope"] = out["ema20"] / out["ema20"].shift(5) - 1
    out["roc5"] = close.pct_change(5)
    atr_pct = out["atr14"] / close
    out["compression"] = (atr_pct / atr_pct.rolling(60).median()).shift(1)
    for window in [10, 20, 40]:
        out[f"prior_high{window}"] = high.rolling(window).max().shift(1)
        out[f"prior_low{window}"] = low.rolling(window).min().shift(1)
        mid = close.rolling(window).mean()
        std = close.rolling(window).std()
        out[f"bb_mid{window}"] = mid
        out[f"bb_std{window}"] = std
    return out


def rule_candidates() -> list[dict]:
    candidates = []
    for ma in [50, 100, 200]:
        for rsi_period in [7, 14]:
            for rsi_entry in [35, 40]:
                for adx_min in [15, 25]:
                    candidates.append({"family": "trend_pullback", "ma": ma, "rsi_period": rsi_period, "rsi_entry": rsi_entry, "adx_min": adx_min})
    for lookback in [10, 20, 40]:
        for adx_min in [15, 25]:
            for compression_max in [0.8, 1.0]:
                candidates.append({"family": "breakout", "lookback": lookback, "adx_min": adx_min, "compression_max": compression_max})
    for window in [10, 20, 40]:
        for band_std in [1.5, 2.0]:
            for rsi_period in [7, 14]:
                for rsi_entry in [25, 35]:
                    candidates.append({"family": "mean_reversion", "window": window, "band_std": band_std, "rsi_period": rsi_period, "rsi_entry": rsi_entry})
    for fast, slow in [(10, 50), (20, 100), (50, 200)]:
        for adx_min in [15, 25]:
            candidates.append({"family": "ma_momentum", "fast": fast, "slow": slow, "adx_min": adx_min})
    for candidate in candidates:
        candidate["entry_id"] = _stable_id(candidate)
    return candidates


def rule_signals(history: pd.DataFrame, state: pd.DataFrame, candidate: dict) -> tuple[pd.Series, pd.Series]:
    close = history["close"]
    family = candidate["family"]
    if family == "trend_pullback":
        ma = state[f"sma{candidate['ma']}"]
        rsi = state[f"rsi{candidate['rsi_period']}"]
        long_signal = (close > ma) & (state["ema20_slope"] > 0) & (rsi <= candidate["rsi_entry"]) & (state["adx14"] >= candidate["adx_min"])
        short_signal = (close < ma) & (state["ema20_slope"] < 0) & (rsi >= 100 - candidate["rsi_entry"]) & (state["adx14"] >= candidate["adx_min"])
    elif family == "breakout":
        long_signal = (close > state[f"prior_high{candidate['lookback']}"]) & (state["adx14"] >= candidate["adx_min"]) & (state["compression"] <= candidate["compression_max"])
        short_signal = (close < state[f"prior_low{candidate['lookback']}"]) & (state["adx14"] >= candidate["adx_min"]) & (state["compression"] <= candidate["compression_max"])
    elif family == "mean_reversion":
        window = candidate["window"]
        upper = state[f"bb_mid{window}"] + candidate["band_std"] * state[f"bb_std{window}"]
        lower = state[f"bb_mid{window}"] - candidate["band_std"] * state[f"bb_std{window}"]
        rsi = state[f"rsi{candidate['rsi_period']}"]
        long_signal = (close < lower) & (rsi <= candidate["rsi_entry"])
        short_signal = (close > upper) & (rsi >= 100 - candidate["rsi_entry"])
    elif family == "ma_momentum":
        fast, slow = state[f"sma{candidate['fast']}"] , state[f"sma{candidate['slow']}"]
        long_signal = (fast > slow) & (state["roc5"] > 0) & (state["adx14"] >= candidate["adx_min"])
        short_signal = (fast < slow) & (state["roc5"] < 0) & (state["adx14"] >= candidate["adx_min"])
    else:
        raise ValueError(f"Familia desconhecida: {family}")
    return long_signal.fillna(False), short_signal.fillna(False)


def exit_candidates() -> list[dict]:
    return [
        {"stop_atr": stop, "target_atr": target, "max_hold": hold}
        for stop in STOP_ATR
        for target in TARGET_ATR
        for hold in MAX_HOLD
    ]


def _choose_side(long_active: bool, short_active: bool, side_mode: str) -> int:
    if side_mode in {"long", "both"} and long_active and not short_active:
        return 1
    if side_mode in {"short", "both"} and short_active and not long_active:
        return -1
    return 0


def simulate_trades(
    history: pd.DataFrame,
    atr: pd.Series,
    long_signal: pd.Series,
    short_signal: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
    exit_params: dict,
    side_mode: str,
    cost_bps_per_side: float,
    setup_id: str,
) -> list[dict]:
    index = history.index
    start_pos = int(index.searchsorted(start, side="left"))
    end_pos = int(index.searchsorted(end, side="right")) - 1
    cost = cost_bps_per_side / 10_000
    trades = []
    decision = max(start_pos, 0)
    max_hold = int(exit_params["max_hold"])
    while decision + max_hold + 1 <= end_pos:
        side = _choose_side(bool(long_signal.iloc[decision]), bool(short_signal.iloc[decision]), side_mode)
        if side == 0 or not np.isfinite(atr.iloc[decision]) or atr.iloc[decision] <= 0:
            decision += 1
            continue
        entry_pos = decision + 1
        entry = float(history["open"].iloc[entry_pos])
        risk = float(atr.iloc[decision]) * float(exit_params["stop_atr"])
        reward = float(atr.iloc[decision]) * float(exit_params["target_atr"])
        stop = entry - side * risk
        target = entry + side * reward
        exit_pos = entry_pos + max_hold
        exit_price = float(history["open"].iloc[exit_pos])
        reason = "time"
        for bar in range(entry_pos, exit_pos):
            open_price = float(history["open"].iloc[bar])
            high = float(history["high"].iloc[bar])
            low = float(history["low"].iloc[bar])
            stop_hit = low <= stop if side == 1 else high >= stop
            target_hit = high >= target if side == 1 else low <= target
            if stop_hit:  # pessimistic ordering when both occur in the same candle
                exit_pos = bar
                exit_price = min(open_price, stop) if side == 1 else max(open_price, stop)
                reason = "stop"
                break
            if target_hit:
                exit_pos = bar
                exit_price = max(open_price, target) if side == 1 else min(open_price, target)
                reason = "target"
                break
        gross_return = side * (exit_price / entry - 1)
        net_return = gross_return - 2 * cost
        trades.append(
            {
                "setup_id": setup_id,
                "decision_date": str(index[decision].date()),
                "entry_date": str(index[entry_pos].date()),
                "exit_date": str(index[exit_pos].date()),
                "side": "long" if side == 1 else "short",
                "entry": round(entry, 6),
                "exit": round(exit_price, 6),
                "stop": round(stop, 6),
                "target": round(target, 6),
                "bars_held": int(exit_pos - entry_pos),
                "exit_reason": reason,
                "gross_return": float(gross_return),
                "net_return": float(net_return),
            }
        )
        decision = exit_pos
    return trades


def trade_metrics(trades: list[dict], start: pd.Timestamp, end: pd.Timestamp) -> dict:
    days = max(1, len(pd.bdate_range(start.normalize(), end.normalize())))
    if not trades:
        return {"trades": 0, "long_trades": 0, "short_trades": 0, "net_return_pct": 0.0, "cagr_pct": 0.0, "sharpe": None, "sortino": None, "max_drawdown_pct": 0.0, "profit_factor": None, "expectancy_pct": None, "win_rate": None, "p_value": None}
    returns = np.asarray([trade["net_return"] for trade in trades], dtype=float)
    daily = pd.Series(0.0, index=pd.bdate_range(start.normalize(), end.normalize(), tz=start.tz))
    for trade, value in zip(trades, returns):
        timestamp = pd.Timestamp(trade["exit_date"], tz=start.tz)
        if timestamp in daily.index:
            daily.loc[timestamp] += value
    equity = (1 + daily).cumprod()
    drawdown = equity / equity.cummax() - 1
    standard_deviation = daily.std(ddof=1)
    downside = daily[daily < 0].std(ddof=1)
    gross_profit = returns[returns > 0].sum()
    gross_loss = -returns[returns < 0].sum()
    years = days / 252
    t_result = stats.ttest_1samp(returns, 0, alternative="greater") if len(returns) >= 3 else None
    return {
        "trades": int(len(trades)),
        "long_trades": int(sum(trade["side"] == "long" for trade in trades)),
        "short_trades": int(sum(trade["side"] == "short" for trade in trades)),
        "net_return_pct": round(float((equity.iloc[-1] - 1) * 100), 3),
        "cagr_pct": round(float((equity.iloc[-1] ** (1 / years) - 1) * 100), 3) if years > 0 and equity.iloc[-1] > 0 else None,
        "sharpe": round(float(daily.mean() / standard_deviation * math.sqrt(252)), 3) if standard_deviation > 0 else None,
        "sortino": round(float(daily.mean() / downside * math.sqrt(252)), 3) if downside > 0 else None,
        "max_drawdown_pct": round(float(drawdown.min() * 100), 3),
        "profit_factor": round(float(gross_profit / gross_loss), 3) if gross_loss > 0 else None,
        "expectancy_pct": round(float(returns.mean() * 100), 4),
        "win_rate": round(float((returns > 0).mean()), 4),
        "p_value": round(float(t_result.pvalue), 6) if t_result is not None and np.isfinite(t_result.pvalue) else None,
    }


def _fold_ranges(dev: pd.DataFrame, folds: list[tuple[np.ndarray, np.ndarray]]) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    return [(dev.iloc[validation].index.min(), dev.iloc[validation].index.max()) for _, validation in folds]


def evaluate_rule_grid(history: pd.DataFrame, dev: pd.DataFrame, folds, config: OperationalConfig) -> tuple[pd.DataFrame, dict[str, dict], dict[str, tuple[pd.Series, pd.Series]]]:
    state = indicator_state(history)
    exits = exit_candidates()
    ranges = _fold_ranges(dev, folds)
    screening_rows = []
    definitions = {}
    signals = {}
    for entry in rule_candidates():
        long_signal, short_signal = rule_signals(history, state, entry)
        signals[entry["entry_id"]] = (long_signal, short_signal)
        screening_exit = {"stop_atr": 1.5, "target_atr": 2.0, "max_hold": 5}
        for side_mode in SIDE_MODES:
            setup_id = f"screen-{entry['entry_id']}-{side_mode}"
            all_trades = []
            fold_metrics = []
            for start, end in ranges:
                trades = simulate_trades(history, state["atr14"], long_signal, short_signal, start, end, screening_exit, side_mode, config.cost_bps_per_side, setup_id)
                all_trades.extend(trades)
                fold_metrics.append(trade_metrics(trades, start, end))
            metrics = trade_metrics(all_trades, ranges[0][0], ranges[-1][1])
            expectancy = [row["expectancy_pct"] for row in fold_metrics if row["expectancy_pct"] is not None]
            screening_rows.append({"entry_id": entry["entry_id"], "family": entry["family"], "side_mode": side_mode, "positive_folds": sum(value > 0 for value in expectancy), "folds_with_trades": len(expectancy), "median_fold_expectancy_pct": round(float(np.median(expectancy)), 4) if expectancy else None, **metrics})

    screening = pd.DataFrame(screening_rows)
    screening["eligible"] = (screening["trades"] >= config.min_trades) & (screening["positive_folds"] >= 3)
    screening = screening.sort_values(["eligible", "positive_folds", "median_fold_expectancy_pct", "sharpe", "trades"], ascending=[False, False, False, False, False])
    finalists = (
        screening.groupby(["family", "side_mode"], sort=False, group_keys=False)
        .head(4)[["entry_id", "side_mode"]]
        .drop_duplicates()
        .to_dict(orient="records")
    )

    entries = {entry["entry_id"]: entry for entry in rule_candidates()}
    rows = []
    for finalist in finalists:
        entry = entries[finalist["entry_id"]]
        side_mode = finalist["side_mode"]
        long_signal, short_signal = signals[entry["entry_id"]]
        for exit_params in exits:
                definition = {"kind": "rule", "entry": entry, "exit": exit_params, "side_mode": side_mode}
                setup_id = _stable_id(definition)
                definitions[setup_id] = definition
                fold_metrics = []
                all_trades = []
                for start, end in ranges:
                    trades = simulate_trades(history, state["atr14"], long_signal, short_signal, start, end, exit_params, side_mode, config.cost_bps_per_side, setup_id)
                    all_trades.extend(trades)
                    fold_metrics.append(trade_metrics(trades, start, end))
                metrics = trade_metrics(all_trades, ranges[0][0], ranges[-1][1])
                expectancy = [row["expectancy_pct"] for row in fold_metrics if row["expectancy_pct"] is not None]
                positive_folds = sum(value > 0 for value in expectancy)
                rows.append(
                    {
                        "setup_id": setup_id,
                        "kind": "rule",
                        "family": entry["family"],
                        "side_mode": side_mode,
                        "positive_folds": positive_folds,
                        "folds_with_trades": len(expectancy),
                        "median_fold_expectancy_pct": round(float(np.median(expectancy)), 4) if expectancy else None,
                        **metrics,
                    }
                )
    table = pd.DataFrame(rows)
    table["eligible"] = (table["trades"] >= config.min_trades) & (table["positive_folds"] >= 3)
    table = table.sort_values(["eligible", "positive_folds", "median_fold_expectancy_pct", "sharpe", "trades"], ascending=[False, False, False, False, False]).reset_index(drop=True)
    table.attrs["screened_entry_side_pairs"] = len(screening)
    table.attrs["tuned_entry_side_pairs"] = len(finalists)
    return table, definitions, signals


def _model(model_name: str, seed: int) -> Pipeline:
    if model_name == "logistic_l1":
        return Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler()), ("model", LogisticRegression(l1_ratio=1.0, solver="liblinear", C=0.05, class_weight="balanced", max_iter=3000, random_state=seed))])
    return Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", RandomForestClassifier(n_estimators=400, max_depth=4, min_samples_leaf=40, max_features="sqrt", class_weight="balanced_subsample", random_state=seed, n_jobs=1))])


def _classification(y_true: pd.Series, probability: np.ndarray) -> dict:
    predicted = probability >= 0.5
    truth = y_true.astype(int).to_numpy()
    return {
        "balanced_accuracy": round(float(balanced_accuracy_score(truth, predicted)), 4),
        "mcc": round(float(matthews_corrcoef(truth, predicted)), 4),
        "precision": round(float(precision_score(truth, predicted, zero_division=0)), 4),
        "recall": round(float(recall_score(truth, predicted, zero_division=0)), 4),
        "brier": round(float(brier_score_loss(truth, probability)), 5),
    }


def ml_probabilities(dev: pd.DataFrame, test: pd.DataFrame, folds, config: OperationalConfig) -> tuple[dict, dict]:
    excluded = {"target_gross_return", "target_net_return", "target_up", "entry_open", "exit_open", "regime"}
    pool = [column for column in dev.columns if column not in excluded and pd.api.types.is_numeric_dtype(dev[column]) and dev[column].isna().mean() < 0.2]
    output = {}
    metadata = {}
    for model_name in ["logistic_l1", "random_forest"]:
        oof = pd.Series(np.nan, index=dev.index, dtype=float)
        selection_counts = {feature: 0 for feature in pool}
        for fold_number, (train_idx, validation_idx) in enumerate(folds):
            train, validation = dev.iloc[train_idx], dev.iloc[validation_idx]
            imputer = SimpleImputer(strategy="median")
            train_imputed = imputer.fit_transform(train[pool])
            mi = mutual_info_classif(train_imputed, train["target_up"].astype(int), random_state=config.seed + fold_number)
            selected = [pool[index] for index in np.argsort(mi)[-15:]]
            for feature in selected:
                selection_counts[feature] += 1
            model = _model(model_name, config.seed + fold_number).fit(train[selected], train["target_up"].astype(int))
            oof.iloc[validation_idx] = model.predict_proba(validation[selected])[:, 1]
        full_imputer = SimpleImputer(strategy="median")
        full_values = full_imputer.fit_transform(dev[pool])
        full_mi = mutual_info_classif(full_values, dev["target_up"].astype(int), random_state=config.seed)
        final_features = [pool[index] for index in np.argsort(full_mi)[-15:]]
        final_model = _model(model_name, config.seed).fit(dev[final_features], dev["target_up"].astype(int))
        test_probability = pd.Series(final_model.predict_proba(test[final_features])[:, 1], index=test.index)
        valid_oof = oof.notna()
        output[model_name] = {"oof": oof, "test": test_probability}
        metadata[model_name] = {
            "oof_metrics": _classification(dev.loc[valid_oof, "target_up"], oof.loc[valid_oof].to_numpy()),
            "holdout_metrics": _classification(test["target_up"], test_probability.to_numpy()),
            "final_features": final_features,
            "fold_selection_frequency": sorted([{"feature": feature, "folds": count} for feature, count in selection_counts.items() if count], key=lambda row: row["folds"], reverse=True),
        }
    return output, metadata


def probability_signals(index: pd.DatetimeIndex, probability: pd.Series, threshold: float) -> tuple[pd.Series, pd.Series]:
    aligned = probability.reindex(index)
    return (aligned >= threshold).fillna(False), (aligned <= 1 - threshold).fillna(False)


def evaluate_ml_grid(history: pd.DataFrame, dev: pd.DataFrame, folds, probabilities: dict, config: OperationalConfig) -> tuple[pd.DataFrame, dict]:
    state = indicator_state(history)
    ranges = _fold_ranges(dev, folds)
    rows = []
    definitions = {}
    for model_name, model_probabilities in probabilities.items():
        for threshold in [0.55, 0.60, 0.65]:
            long_signal, short_signal = probability_signals(history.index, model_probabilities["oof"], threshold)
            for exit_params in exit_candidates():
                for side_mode in SIDE_MODES:
                    definition = {"kind": "ml", "model": model_name, "probability_threshold": threshold, "exit": exit_params, "side_mode": side_mode}
                    setup_id = _stable_id(definition)
                    definitions[setup_id] = definition
                    all_trades = []
                    fold_metrics = []
                    for start, end in ranges:
                        trades = simulate_trades(history, state["atr14"], long_signal, short_signal, start, end, exit_params, side_mode, config.cost_bps_per_side, setup_id)
                        all_trades.extend(trades)
                        fold_metrics.append(trade_metrics(trades, start, end))
                    metrics = trade_metrics(all_trades, ranges[0][0], ranges[-1][1])
                    expectancy = [row["expectancy_pct"] for row in fold_metrics if row["expectancy_pct"] is not None]
                    rows.append({"setup_id": setup_id, "kind": "ml", "family": model_name, "side_mode": side_mode, "positive_folds": sum(value > 0 for value in expectancy), "folds_with_trades": len(expectancy), "median_fold_expectancy_pct": round(float(np.median(expectancy)), 4) if expectancy else None, **metrics})
    table = pd.DataFrame(rows)
    table["eligible"] = (table["trades"] >= config.min_trades) & (table["positive_folds"] >= 3)
    table = table.sort_values(["eligible", "positive_folds", "median_fold_expectancy_pct", "sharpe", "trades"], ascending=[False, False, False, False, False]).reset_index(drop=True)
    return table, definitions


def diverse_selection(table: pd.DataFrame, config: OperationalConfig) -> list[str]:
    selected = []
    counts = {}
    for row in table.itertuples(index=False):
        key = (row.kind, row.family, row.side_mode)
        if counts.get(key, 0) >= config.max_per_family_side:
            continue
        selected.append(row.setup_id)
        counts[key] = counts.get(key, 0) + 1
        if len(selected) >= config.final_candidates:
            break
    return selected


def final_evaluation(
    history: pd.DataFrame,
    test: pd.DataFrame,
    setup_ids: list[str],
    definitions: dict,
    rule_signals_cache: dict,
    ml_probability: dict,
    config: OperationalConfig,
) -> tuple[pd.DataFrame, dict[str, list[dict]]]:
    state = indicator_state(history)
    start, end = test.index.min(), test.index.max()
    rows = []
    logs = {}
    p_values = {}
    for setup_id in setup_ids:
        definition = definitions[setup_id]
        if definition["kind"] == "rule":
            long_signal, short_signal = rule_signals_cache[definition["entry"]["entry_id"]]
        else:
            long_signal, short_signal = probability_signals(history.index, ml_probability[definition["model"]]["test"], definition["probability_threshold"])
        trades = simulate_trades(history, state["atr14"], long_signal, short_signal, start, end, definition["exit"], definition["side_mode"], config.cost_bps_per_side, setup_id)
        for trade in trades:
            decision_date = pd.Timestamp(trade["decision_date"], tz=test.index.tz)
            trade["regime"] = str(test.loc[decision_date, "regime"]) if decision_date in test.index else "unknown"
        metrics = trade_metrics(trades, start, end)
        rows.append({"setup_id": setup_id, "kind": definition["kind"], "family": definition["entry"]["family"] if definition["kind"] == "rule" else definition["model"], "side_mode": definition["side_mode"], "definition": json.dumps(definition, sort_keys=True), **metrics})
        logs[setup_id] = trades
        p_values[setup_id] = metrics["p_value"]
    q_values = _bh_adjust(p_values)
    for row in rows:
        row["bh_q_value"] = q_values[row["setup_id"]]
        row["classification"] = classify_setup(row, config)
    table = pd.DataFrame(rows).sort_values(["bh_q_value", "trades", "expectancy_pct"], ascending=[True, False, False], na_position="last").reset_index(drop=True)
    return table, logs


def stability_evidence(holdout: pd.DataFrame, logs: dict[str, list[dict]], start: pd.Timestamp, end: pd.Timestamp) -> tuple[list[dict], list[dict]]:
    yearly = []
    regimes = []
    for setup_id in holdout.head(5)["setup_id"].tolist():
        trades = logs.get(setup_id, [])
        years = sorted({int(trade["exit_date"][:4]) for trade in trades})
        for year in years:
            subset = [trade for trade in trades if int(trade["exit_date"][:4]) == year]
            year_start = max(start, pd.Timestamp(f"{year}-01-01", tz=start.tz))
            year_end = min(end, pd.Timestamp(f"{year}-12-31", tz=start.tz))
            yearly.append({"setup_id": setup_id, "year": year, **trade_metrics(subset, year_start, year_end)})
        for regime in sorted({trade.get("regime", "unknown") for trade in trades}):
            subset = [trade for trade in trades if trade.get("regime", "unknown") == regime]
            regimes.append({"setup_id": setup_id, "regime": regime, **trade_metrics(subset, start, end)})
    return yearly, regimes


def classify_setup(row: dict, config: OperationalConfig) -> str:
    if row["trades"] < config.min_trades:
        return "precisa de mais dados"
    if row["expectancy_pct"] is None or row["expectancy_pct"] <= 0:
        return "rejeitado"
    if row.get("bh_q_value") is not None and row["bh_q_value"] <= 0.10 and row.get("short_trades", 0) + row.get("long_trades", 0) >= config.min_trades:
        return "aprovado para paper trading"
    return "experimental"


def transfer_evaluation(history: pd.DataFrame, test: pd.DataFrame, final_table: pd.DataFrame, definitions: dict, config: OperationalConfig) -> pd.DataFrame:
    state = indicator_state(history)
    signals_cache = {}
    rows = []
    for row in final_table.head(10).to_dict(orient="records"):
        definition = definitions[row["setup_id"]]
        if definition["kind"] != "rule":
            continue
        entry_id = definition["entry"]["entry_id"]
        if entry_id not in signals_cache:
            signals_cache[entry_id] = rule_signals(history, state, definition["entry"])
        long_signal, short_signal = signals_cache[entry_id]
        trades = simulate_trades(history, state["atr14"], long_signal, short_signal, test.index.min(), test.index.max(), definition["exit"], definition["side_mode"], config.cost_bps_per_side, row["setup_id"])
        rows.append({"setup_id": row["setup_id"], **trade_metrics(trades, test.index.min(), test.index.max())})
    return pd.DataFrame(rows)


def analyse_market(market: str, frames: dict, config: OperationalConfig) -> dict:
    primary_symbol = TARGETS[market]["primary"]
    transfer_symbol = TARGETS[market]["transfer"]
    research_config = ResearchConfig(period=config.period, horizon=config.horizon, holdout_years=config.holdout_years, development_folds=config.development_folds, cost_bps_per_side=config.cost_bps_per_side, min_train_bars=config.min_train_bars, min_trades=config.min_trades, seed=config.seed)
    dataset = build_dataset(frames[primary_symbol], frames, market, research_config)
    dev, test, folds = temporal_split(dataset, research_config)
    rule_table, rule_definitions, rule_signal_cache = evaluate_rule_grid(frames[primary_symbol], dev, folds, config)
    ml_probability, ml_metadata = ml_probabilities(dev, test, folds, config)
    ml_table, ml_definitions = evaluate_ml_grid(frames[primary_symbol], dev, folds, ml_probability, config)
    combined = pd.concat([rule_table, ml_table], ignore_index=True).sort_values(["eligible", "positive_folds", "median_fold_expectancy_pct", "sharpe", "trades"], ascending=[False, False, False, False, False]).reset_index(drop=True)
    definitions = {**rule_definitions, **ml_definitions}
    selected = diverse_selection(combined, config)
    holdout, trade_logs = final_evaluation(frames[primary_symbol], test, selected, definitions, rule_signal_cache, ml_probability, config)
    yearly, regimes = stability_evidence(holdout, trade_logs, test.index.min(), test.index.max())

    transfer_dataset = build_dataset(frames[transfer_symbol], frames, market, research_config)
    _, transfer_test, _ = temporal_split(transfer_dataset, research_config)
    transfer = transfer_evaluation(frames[transfer_symbol], transfer_test, holdout, definitions, config)

    return {
        "market": market,
        "primary_symbol": primary_symbol,
        "transfer_symbol": transfer_symbol,
        "development_period": [str(dev.index.min().date()), str(dev.index.max().date())],
        "holdout_period": [str(test.index.min().date()), str(test.index.max().date())],
        "rule_configurations": int(len(rule_table)),
        "ml_configurations": int(len(ml_table)),
        "development_ranking": combined.head(200).to_dict(orient="records"),
        "holdout": holdout.to_dict(orient="records"),
        "transfer": transfer.to_dict(orient="records"),
        "buy_and_hold": buy_and_hold_metrics(frames[primary_symbol], test.index.min(), test.index.max(), research_config),
        "yearly_holdout": yearly,
        "regime_holdout": regimes,
        "definitions": {setup_id: definitions[setup_id] for setup_id in selected},
        "ml_metadata": ml_metadata,
        "trade_logs": {setup_id: trades for setup_id, trades in trade_logs.items() if setup_id in holdout.head(5)["setup_id"].tolist()},
    }


def markdown_report(payload: dict) -> str:
    lines = [
        "# Pesquisa de setups operacionais para Nasdaq e ouro",
        "",
        "## Escopo operacional",
        "",
        "Cada candidato define direção, entrada e saída. O sinal usa o fechamento de t, a entrada ocorre na abertura de t+1, e a saída acontece por stop ATR, alvo ATR ou tempo máximo. Quando stop e alvo aparecem na mesma barra diária, o teste assume stop primeiro. Spread, slippage e comissão são agregados em 7 bps por lado.",
        "",
        "A pesquisa diária identifica o pregão de entrada e saída. Ela não identifica a hora intradiária, pois o projeto não possui histórico intradiário suficiente de NQ/GC nem dados bid/ask ou de negócios.",
        "",
        "## Descoberta por regras e IA",
        "",
        "A grade determinística combinou trend pullback, breakout, mean reversion e momentum de médias com parâmetros vizinhos. Regressão logística L1 e Random Forest receberam features técnicas e intermercado selecionadas por mutual information dentro de cada fold. Probabilidades foram transformadas em entradas long/short e testadas com as mesmas saídas das regras.",
        "",
        "Parâmetros foram ordenados somente em cinco folds expanding-window. Os vinte candidatos finais foram congelados antes do holdout de dois anos. A correção Benjamini-Hochberg foi aplicada aos resultados finais.",
    ]
    overall_approved = 0
    for market in ["nasdaq", "gold"]:
        result = payload["results"][market]
        transfer_map = {row["setup_id"]: row for row in result["transfer"]}
        lines.extend(["", f"## {market.title()}", "", f"Primário: {result['primary_symbol']}. Transferência: {result['transfer_symbol']}. Desenvolvimento: {result['development_period'][0]} a {result['development_period'][1]}. Holdout: {result['holdout_period'][0]} a {result['holdout_period'][1]}.", "", f"Foram avaliadas {result['rule_configurations']} combinações de regras e {result['ml_configurations']} combinações de IA no desenvolvimento.", "", "| # | Tipo | Família | Lado | Trades | Long | Short | Expectancy % | Sharpe | DD % | PF | q BH | Transfer exp. % | Status |", "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"])
        for rank, row in enumerate(result["holdout"], start=1):
            transfer = transfer_map.get(row["setup_id"], {})
            overall_approved += row["classification"] == "aprovado para paper trading"
            lines.append(f"| {rank} | {row['kind']} | {row['family']} | {row['side_mode']} | {row['trades']} | {row['long_trades']} | {row['short_trades']} | {row['expectancy_pct']} | {row['sharpe']} | {row['max_drawdown_pct']} | {row['profit_factor']} | {row['bh_q_value']} | {transfer.get('expectancy_pct')} | {row['classification']} |")
        lines.extend(["", "### Parâmetros dos cinco primeiros", ""])
        for row in result["holdout"][:5]:
            lines.append(f"- `{row['setup_id']}`: `{row['definition']}`")
        lines.extend(["", f"Buy-and-hold no mesmo holdout: retorno líquido {result['buy_and_hold']['net_return_pct']}%, Sharpe {result['buy_and_hold']['sharpe']} e drawdown {result['buy_and_hold']['max_drawdown_pct']}%.", "", "### Estabilidade do primeiro setup", "", "| Corte | Subamostra | Trades | Expectancy % | Sharpe | DD % |", "|---|---|---:|---:|---:|---:|"])
        top_setup = result["holdout"][0]["setup_id"] if result["holdout"] else None
        for row in result["yearly_holdout"]:
            if row["setup_id"] == top_setup:
                lines.append(f"| ano | {row['year']} | {row['trades']} | {row['expectancy_pct']} | {row['sharpe']} | {row['max_drawdown_pct']} |")
        for row in result["regime_holdout"]:
            if row["setup_id"] == top_setup:
                lines.append(f"| regime | {row['regime']} | {row['trades']} | {row['expectancy_pct']} | {row['sharpe']} | {row['max_drawdown_pct']} |")
        lines.extend(["", "### IA", "", "| Modelo | OOF balanced acc. | OOF MCC | OOF Brier | Holdout balanced acc. | Holdout MCC | Holdout Brier |", "|---|---:|---:|---:|---:|---:|---:|"])
        for model, metadata in result["ml_metadata"].items():
            oof, holdout = metadata["oof_metrics"], metadata["holdout_metrics"]
            lines.append(f"| {model} | {oof['balanced_accuracy']} | {oof['mcc']} | {oof['brier']} | {holdout['balanced_accuracy']} | {holdout['mcc']} | {holdout['brier']} |")
            lines.append(f"\nFeatures finais de {model}: {', '.join(metadata['final_features'])}.")
    decision = "Há setup aprovado apenas para paper trading; nenhuma operação real é autorizada." if overall_approved else "Nenhum setup foi aprovado para paper trading. Os candidatos positivos permanecem experimentais ou precisam de mais dados."
    lines.extend(
        [
            "",
            "## Decisão final",
            "",
            decision,
            "",
            "IA ajuda a pesquisar interações e filtrar hipóteses, mas só agrega valor se superar regras simples no holdout líquido. Nesta implementação, classificação e resultado econômico são reportados separadamente; acurácia isolada não promove um setup.",
            "",
            "## Limitações e próximo experimento",
            "",
            "O preenchimento diário não modela ordem dentro da barra, fila, spread variável ou notícias. A hipótese stop-first torna barras ambíguas pessimistas. Séries contínuas NQ=F e GC=F podem conter efeitos de rollover. Para descobrir hora de entrada, o próximo dataset deve conter ao menos 3 a 5 anos de barras de 5 ou 15 minutos, sessão e timezone normalizados, bid/ask ou spread, volume de negócios e calendário macro point-in-time.",
            "",
            "## Fontes",
            "",
            "1. CME Group. [E-mini Nasdaq-100 Futures and Options](https://www.cmegroup.com/trading/equity-index/files/emini-nasdaq-100-futures-options.pdf). Especificações de NQ.",
            "2. CME Group. [Gold Futures Contract Specifications](https://www.cmegroup.com/trading/metals/files/fact-card-gold-futures-options.pdf). Especificações de GC.",
            "3. Bailey, D. H.; López de Prado, M. [The Deflated Sharpe Ratio](https://doi.org/10.2139/ssrn.2460551). Múltiplos testes e seleção de backtests.",
            "4. Bailey, D. H.; Borwein, J.; López de Prado, M.; Zhu, Q. [The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf). Risco de selecionar parâmetros por acaso.",
            "5. Kelly, B.; Malamud, S.; Zhou, K. [The Virtue of Complexity in Return Prediction](https://www.nber.org/papers/w30217). Motivação para testar interações complexas, condicionada a avaliação fora da amostra.",
            "6. scikit-learn. [Permutation feature importance](https://scikit-learn.org/stable/modules/permutation_importance.html). Interpretação de modelos apenas após validação.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(payload: dict) -> dict:
    output_dir = _output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.md"
    result_path = output_dir / "results.json"
    report_path.write_text(markdown_report(payload), encoding="utf-8")
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    csv_paths = []
    for market, result in payload["results"].items():
        for key in ["development_ranking", "holdout", "transfer", "yearly_holdout", "regime_holdout"]:
            path = output_dir / f"{market}_{key}.csv"
            pd.DataFrame(result[key]).to_csv(path, index=False)
            csv_paths.append(path)
        trade_rows = [trade for trades in result["trade_logs"].values() for trade in trades]
        path = output_dir / f"{market}_top_trades.csv"
        pd.DataFrame(trade_rows).to_csv(path, index=False)
        csv_paths.append(path)
    manifest = write_manifest(
        result_path,
        command="python scripts/operational_setup_research.py --cache-only",
        parameters=payload["config"],
        input_paths=sorted((ROOT / "data" / "research" / "nasdaq_gold_raw").glob("*.csv")),
        data_gate=payload["data_audit"],
        extra={"report": str(report_path.relative_to(ROOT)), "csv_outputs": [str(path.relative_to(ROOT)) for path in csv_paths]},
    )
    return {"report": str(report_path), "results": str(result_path), "manifest": str(manifest), "csv": [str(path) for path in csv_paths]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/operational_setup_research.json")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--cache-only", action="store_true")
    args = parser.parse_args()
    config_path = ROOT / args.config
    config = OperationalConfig(**json.loads(config_path.read_text(encoding="utf-8"))) if config_path.exists() else OperationalConfig()
    research_config = ResearchConfig(period=config.period, horizon=config.horizon, holdout_years=config.holdout_years, development_folds=config.development_folds, cost_bps_per_side=config.cost_bps_per_side, min_train_bars=config.min_train_bars, min_trades=config.min_trades, seed=config.seed)
    frames, audit = load_market_data(research_config, refresh=args.refresh, cache_only=args.cache_only)
    results = {}
    for market in ["nasdaq", "gold"]:
        print(f"Pesquisando setups de {market}...", flush=True)
        results[market] = analyse_market(market, frames, config)
    payload = {"schema_version": "operational-setup-research-v1", "created_at": datetime.now(timezone.utc).isoformat(), "config": asdict(config), "timing": "signal close(t), entry open(t+1), ATR exits or time exit", "data_audit": audit, "results": results}
    print(json.dumps(write_outputs(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
