"""Large data/feature audit focused on finding a statistical edge.

This is intentionally stricter than a normal EDA:

1. Build one clean panel by (symbol, date) using the same prepared market
   data as the live simulator.
2. Create candidate features from market structure, momentum, volatility,
   volume, relative strength and macro context.
3. Score features with daily cross-sectional IC instead of pooled accuracy.
4. Validate the best training-only signal on later dates with walk-forward
   folds and a simple long/short quantile spread.
5. Save a JSON report in data/statistical_edge_audit.json.

Run:
    python -m scripts.statistical_edge_audit
    MARKET_HISTORY_PERIOD=5y python -m scripts.statistical_edge_audit
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from app import indicators
from app import paper_simulator as sim
from app.market_data import macro_data
from scripts.compare_recommendations import DEFAULT_SYMBOLS, _load_prepared, _symbols
from scripts.research_folds import date_based_folds

pd.set_option("display.width", 180)

OUT_PATH = Path("data/statistical_edge_audit.json")
HORIZONS_DAYS = [1, 3, 5, 10, 20]
PRIMARY_HORIZON = 5
MIN_SYMBOLS_PER_DAY = 10
TOP_FEATURES_TO_VALIDATE = 8
QUANTILE = 0.2
WALK_FORWARD_FOLDS = 5
EMBARGO_DAYS = 5


def _normalize_index(index: pd.Index) -> pd.DatetimeIndex:
    idx = pd.to_datetime(index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    return idx.normalize()


def _clean_series(series: pd.Series) -> pd.Series:
    out = series.copy()
    out.index = _normalize_index(out.index)
    return out[~out.index.duplicated(keep="last")].sort_index()


def _safe_float(value) -> float | None:
    if value is None or pd.isna(value) or np.isinf(value):
        return None
    return float(value)


def _series_at(series: pd.Series, position: int) -> float | None:
    if position >= len(series):
        return None
    return _safe_float(series.iloc[position])


def _spearman(x: pd.Series, y: pd.Series) -> float | None:
    if len(x) < 3 or x.nunique(dropna=True) < 2 or y.nunique(dropna=True) < 2:
        return None
    value = x.rank().corr(y.rank())
    return _safe_float(value)


def _t_stat(values: pd.Series) -> float | None:
    values = values.dropna()
    if len(values) < 3:
        return None
    std = float(values.std())
    if std == 0:
        return None
    return float(values.mean() / std * math.sqrt(len(values)))


@lru_cache(maxsize=8)
def _load_macro_close(key: str) -> pd.Series:
    try:
        history = macro_data.get_macro_history(key)
    except Exception:
        history = pd.DataFrame()
    if history.empty or "close" not in history:
        return pd.Series(dtype=float)
    return _clean_series(history["close"])


def _macro_context(index: pd.Index) -> dict[str, pd.Series]:
    target_index = _normalize_index(index)
    aligned: dict[str, pd.Series] = {}
    for key in ("DXY", "US10Y"):
        close = _load_macro_close(key)
        if close.empty:
            aligned[key] = pd.Series(index=target_index, dtype=float)
        else:
            aligned[key] = close.reindex(target_index, method="ffill")
            aligned[key].index = target_index
    return aligned


def _benchmark_by_date(benchmark: dict | None) -> dict[str, pd.Series]:
    if not benchmark:
        return {}
    history = benchmark["history"]
    close = _clean_series(history["close"])
    return {
        "close": close,
        "return_20d": close.pct_change(20) * 100,
        "return_5d": close.pct_change(5) * 100,
    }


def _candidate_series(symbol: str, data: dict, benchmark_by_date: dict[str, pd.Series]) -> dict[str, pd.Series]:
    history = data["history"]
    close = history["close"]
    high = history["high"]
    low = history["low"]
    volume = history["volume"]
    date_index = _normalize_index(history.index)

    adx = indicators.adx(high, low, close, 14)
    ema20 = indicators.ema(close, 20)
    ema50 = indicators.ema(close, 50)
    sma20 = data["sma20"]
    sma50 = data["sma50"]
    recent_high = data["recent_high20"]
    recent_low = data["recent_low20"]
    rolling_vol5 = close.pct_change().rolling(5, min_periods=5).std() * math.sqrt(252) * 100
    rolling_vol20 = data["annualized_volatility"]
    volume_mean20 = volume.rolling(20, min_periods=20).mean()
    volume_std20 = volume.rolling(20, min_periods=20).std().replace(0, np.nan)
    macro = _macro_context(history.index)

    close_pos_20d = (close - recent_low) / (recent_high - recent_low).replace(0, np.nan)
    benchmark_return20 = benchmark_by_date.get("return_20d", pd.Series(dtype=float)).reindex(date_index)
    benchmark_return5 = benchmark_by_date.get("return_5d", pd.Series(dtype=float)).reindex(date_index)
    dxy_return_5d = macro["DXY"].pct_change(5) * 100
    us10y_change_5d = macro["US10Y"].diff(5)
    rel_ret_5d = close.pct_change(5) * 100 - benchmark_return5.to_numpy()
    rel_ret_20d = close.pct_change(20) * 100 - benchmark_return20.to_numpy()
    ema_gap = (ema20 / ema50 - 1) * 100

    features = {
        "ret_1d": close.pct_change(1) * 100,
        "ret_5d": close.pct_change(5) * 100,
        "ret_20d": close.pct_change(20) * 100,
        "mom_accel_5v20": close.pct_change(5) * 100 - (close.pct_change(20) * 100 / 4),
        "dist_sma20_pct": (close / sma20 - 1) * 100,
        "dist_sma50_pct": (close / sma50 - 1) * 100,
        "ema20_50_gap_pct": ema_gap,
        "high20_breakout_pct": (close / recent_high - 1) * 100,
        "low20_rebound_pct": (close / recent_low - 1) * 100,
        "close_position_20d": close_pos_20d,
        "range_pct": (high - low) / close * 100,
        "volume_z20": (volume - volume_mean20) / volume_std20,
        "volume_ratio_5d_change": data["volume_ratio"] - data["volume_ratio"].shift(5),
        "rsi_centered": data["rsi"] - 50,
        "rsi_momentum_3d": data["rsi"] - data["rsi"].shift(3),
        "macd_hist_slope_3d": data["macd"]["histogram"] - data["macd"]["histogram"].shift(3),
        "adx14": adx["adx"],
        "di_diff": adx["plus_di"] - adx["minus_di"],
        "realized_vol_5d": rolling_vol5,
        "vol_ratio_5v20": rolling_vol5 / rolling_vol20.replace(0, np.nan),
        "rel_ret_5d_vs_qqq": rel_ret_5d,
        "rel_ret_20d_vs_qqq": rel_ret_20d,
        "dxy_return_5d": dxy_return_5d,
        "us10y_change_5d": us10y_change_5d,
        "dxy_x_rel_ret_20d": dxy_return_5d.to_numpy() * rel_ret_20d,
        "dxy_x_volatility": dxy_return_5d.to_numpy() * rolling_vol20,
        "us10y_x_ema_gap": us10y_change_5d.to_numpy() * ema_gap,
        "us10y_x_rel_ret_20d": us10y_change_5d.to_numpy() * rel_ret_20d,
        "us10y_x_volatility": us10y_change_5d.to_numpy() * rolling_vol20,
    }
    for name, series in features.items():
        series = pd.Series(series, index=history.index) if not isinstance(series, pd.Series) else series
        series.index = date_index
        features[name] = series
    return features


def _audit_coverage(prepared: dict, skipped: list[str]) -> list[dict]:
    rows = []
    for symbol, data in prepared.items():
        history = data["history"]
        dates = _normalize_index(history.index)
        gaps = pd.Series(dates).diff().dt.days.dropna()
        rows.append(
            {
                "symbol": symbol,
                "candles": int(len(history)),
                "start": str(dates.min().date()),
                "end": str(dates.max().date()),
                "duplicate_dates": int(pd.Index(dates).duplicated().sum()),
                "max_gap_days": int(gaps.max()) if not gaps.empty else 0,
                "suspicious_gaps_gt5d": int((gaps > 5).sum()),
                "missing_ohlcv_cells": int(history[["open", "high", "low", "close", "volume"]].isna().sum().sum()),
            }
        )
    for symbol in skipped:
        rows.append({"symbol": symbol, "status": "skipped_insufficient_history"})
    return rows


def _build_panel(prepared: dict, benchmark: dict | None) -> tuple[pd.DataFrame, list[str]]:
    rows = []
    benchmark_by_date = _benchmark_by_date(benchmark)
    candidate_names: list[str] = []
    max_horizon = max(HORIZONS_DAYS)

    for symbol, data in prepared.items():
        history = data["history"]
        dates = _normalize_index(history.index)
        candidates = _candidate_series(symbol, data, benchmark_by_date)
        candidate_names = list(candidates)

        limit = len(history) - max_horizon
        for i in range(limit):
            base = sim.feature_vector(data, i, benchmark)
            if base is None:
                continue
            price = float(history["close"].iloc[i])
            row = {"symbol": symbol, "date": dates[i]}
            row.update(dict(zip(sim.FEATURE_NAMES, base)))
            for name in candidate_names:
                row[name] = _series_at(candidates[name], i)
            for horizon in HORIZONS_DAYS:
                future_price = float(history["close"].iloc[i + horizon])
                row[f"fwd_return_{horizon}d"] = (future_price / price - 1) * 100
            rows.append(row)

    panel = pd.DataFrame(rows)
    feature_names = list(dict.fromkeys(sim.FEATURE_NAMES + candidate_names))
    panel = panel.replace([np.inf, -np.inf], np.nan)
    return panel, feature_names


def _feature_quality(panel: pd.DataFrame, feature_names: list[str]) -> list[dict]:
    rows = []
    for feature in feature_names:
        values = panel[feature]
        rows.append(
            {
                "feature": feature,
                "nan_pct": round(float(values.isna().mean() * 100), 2),
                "unique_values": int(values.nunique(dropna=True)),
                "mean": round(float(values.mean()), 6) if values.notna().any() else None,
                "std": round(float(values.std()), 6) if values.notna().any() else None,
                "p01": round(float(values.quantile(0.01)), 6) if values.notna().any() else None,
                "p99": round(float(values.quantile(0.99)), 6) if values.notna().any() else None,
            }
        )
    return rows


def _daily_ic(panel: pd.DataFrame, feature: str, target: str) -> pd.Series:
    values = {}
    for date, group in panel[["date", feature, target]].dropna().groupby("date"):
        if len(group) < MIN_SYMBOLS_PER_DAY:
            continue
        ic = _spearman(group[feature], group[target])
        if ic is not None:
            values[date] = ic
    return pd.Series(values, dtype=float)


def _ic_table(panel: pd.DataFrame, feature_names: list[str], horizon: int) -> pd.DataFrame:
    target = f"fwd_return_{horizon}d"
    rows = []
    for feature in feature_names:
        ic = _daily_ic(panel, feature, target)
        if ic.empty:
            continue
        rows.append(
            {
                "feature": feature,
                "horizon_days": horizon,
                "days": int(len(ic)),
                "mean_ic": round(float(ic.mean()), 5),
                "median_ic": round(float(ic.median()), 5),
                "ic_ir": round(float(ic.mean() / ic.std()), 5) if float(ic.std()) != 0 else None,
                "t_stat": round(_t_stat(ic), 3) if _t_stat(ic) is not None else None,
                "positive_day_rate": round(float((ic > 0).mean()), 4),
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("mean_ic", key=lambda s: s.abs(), ascending=False)
    return out


def _quantile_spread(group: pd.DataFrame, feature: str, target: str, sign: int) -> float | None:
    group = group[["symbol", feature, target]].dropna()
    if len(group) < MIN_SYMBOLS_PER_DAY:
        return None
    n = max(1, int(len(group) * QUANTILE))
    ranked = group.sort_values(feature, ascending=True)
    low_leg = ranked.head(n)[target].mean()
    high_leg = ranked.tail(n)[target].mean()
    return _safe_float((high_leg - low_leg) * sign)


def _spread_stats(spreads: pd.Series) -> dict:
    spreads = spreads.dropna()
    if spreads.empty:
        return {"days": 0}
    hit_rate = float((spreads > 0).mean())
    return {
        "days": int(len(spreads)),
        "mean_spread_pct": round(float(spreads.mean()), 5),
        "median_spread_pct": round(float(spreads.median()), 5),
        "t_stat": round(_t_stat(spreads), 3) if _t_stat(spreads) is not None else None,
        "hit_rate": round(hit_rate, 4),
        "annualized_spread_approx_pct": round(float(spreads.mean() * 252 / PRIMARY_HORIZON), 2),
    }


def _validate_walk_forward(panel: pd.DataFrame, primary_ic: pd.DataFrame) -> list[dict]:
    if primary_ic.empty:
        return []
    target = f"fwd_return_{PRIMARY_HORIZON}d"
    folds = date_based_folds(panel["date"], WALK_FORWARD_FOLDS, window_days=panel["date"].nunique(), embargo_days=EMBARGO_DAYS)
    rows = []
    for fold_idx in range(1, len(folds)):
        holdout_start, holdout_end = folds[fold_idx]
        train_end = holdout_start - pd.Timedelta(days=EMBARGO_DAYS)
        train = panel[panel["date"] < train_end]
        holdout = panel[(panel["date"] >= holdout_start) & (panel["date"] < holdout_end)]
        if train.empty or holdout.empty:
            continue

        train_scores = []
        for feature in primary_ic["feature"].head(30):
            ic = _daily_ic(train, feature, target)
            if len(ic) < 20:
                continue
            mean_ic = float(ic.mean())
            train_scores.append((feature, mean_ic, abs(mean_ic)))
        if not train_scores:
            continue
        train_scores.sort(key=lambda row: row[2], reverse=True)
        selected = train_scores[:TOP_FEATURES_TO_VALIDATE]

        for feature, mean_ic, _ in selected:
            sign = 1 if mean_ic >= 0 else -1
            spreads = {}
            for date, group in holdout.groupby("date"):
                spread = _quantile_spread(group, feature, target, sign)
                if spread is not None:
                    spreads[date] = spread
            stats = _spread_stats(pd.Series(spreads, dtype=float))
            rows.append(
                {
                    "fold": fold_idx,
                    "feature": feature,
                    "train_mean_ic": round(mean_ic, 5),
                    "direction_from_train": "high_feature_long" if sign > 0 else "low_feature_long",
                    "holdout_start": str(holdout_start.date()),
                    "holdout_end": str(holdout_end.date()),
                    **stats,
                }
            )
    return rows


def _consensus_signal_validation(panel: pd.DataFrame, primary_ic: pd.DataFrame) -> dict:
    target = f"fwd_return_{PRIMARY_HORIZON}d"
    if primary_ic.empty:
        return {}
    selected = primary_ic.head(TOP_FEATURES_TO_VALIDATE).copy()
    scored = panel[["symbol", "date", target]].copy()
    for row in selected.itertuples(index=False):
        feature = row.feature
        sign = 1 if row.mean_ic >= 0 else -1
        ranked = panel.groupby("date")[feature].rank(pct=True)
        scored[f"rank_{feature}"] = sign * (ranked - 0.5)
    rank_cols = [col for col in scored.columns if col.startswith("rank_")]
    scored["consensus_edge_score"] = scored[rank_cols].mean(axis=1)

    spreads = {}
    for date, group in scored.groupby("date"):
        spread = _quantile_spread(group, "consensus_edge_score", target, 1)
        if spread is not None:
            spreads[date] = spread
    return {
        "features": selected["feature"].tolist(),
        "stats": _spread_stats(pd.Series(spreads, dtype=float)),
    }


def main() -> None:
    symbols = _symbols() or DEFAULT_SYMBOLS
    prepared, benchmark, skipped = _load_prepared(symbols)
    if not prepared:
        raise SystemExit("Nenhum simbolo com historico suficiente para auditar.")

    panel, feature_names = _build_panel(prepared, benchmark)
    coverage = _audit_coverage(prepared, skipped)
    quality = _feature_quality(panel, feature_names)
    usable_features = [
        row["feature"]
        for row in quality
        if row["nan_pct"] <= 15 and row["unique_values"] >= 5 and row["std"] not in (None, 0)
    ]

    ic_by_horizon = {str(h): _ic_table(panel, usable_features, h) for h in HORIZONS_DAYS}
    primary_ic = ic_by_horizon[str(PRIMARY_HORIZON)]
    validation = _validate_walk_forward(panel, primary_ic)
    consensus = _consensus_signal_validation(panel, primary_ic)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbols_requested": symbols,
        "symbols_used": sorted(prepared),
        "symbols_skipped": skipped,
        "rows": int(len(panel)),
        "date_start": str(panel["date"].min().date()) if not panel.empty else None,
        "date_end": str(panel["date"].max().date()) if not panel.empty else None,
        "feature_count_total": len(feature_names),
        "feature_count_usable": len(usable_features),
        "coverage": coverage,
        "feature_quality": quality,
        "top_ic_by_horizon": {
            horizon: table.head(15).to_dict(orient="records")
            for horizon, table in ic_by_horizon.items()
        },
        "walk_forward_quantile_validation": validation,
        "consensus_signal": consensus,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("AUDITORIA ESTATISTICA DE DADOS + FEATURE ENGINEERING")
    print("=" * 72)
    print(f"Simbolos usados: {len(prepared)} | amostras: {len(panel)} | features usaveis: {len(usable_features)}")
    print(f"Periodo: {report['date_start']} a {report['date_end']}")
    print(f"Relatorio salvo em: {OUT_PATH}")

    print("\nTOP FEATURES POR IC CROSS-SECTIONAL")
    print(primary_ic.head(15).to_string(index=False))

    validation_df = pd.DataFrame(validation)
    print("\nVALIDACAO WALK-FORWARD LONG/SHORT POR QUANTIS")
    if validation_df.empty:
        print("Sem folds validos para validacao.")
    else:
        aggregate = (
            validation_df.groupby("feature")
            .agg(
                folds=("fold", "count"),
                mean_train_ic=("train_mean_ic", "mean"),
                mean_holdout_spread_pct=("mean_spread_pct", "mean"),
                mean_hit_rate=("hit_rate", "mean"),
                best_t_stat=("t_stat", "max"),
            )
            .sort_values("mean_holdout_spread_pct", ascending=False)
        )
        print(aggregate.head(15).round(5).to_string())

    print("\nCONSENSO MULTI-FEATURE")
    print(json.dumps(consensus, ensure_ascii=False, indent=2))

    print("\nLEITURA")
    if validation_df.empty:
        print("A auditoria criou as features, mas nao houve historico suficiente para uma validacao walk-forward robusta.")
    else:
        best = validation_df.sort_values("mean_spread_pct", ascending=False).iloc[0]
        if float(best.get("mean_spread_pct", 0)) > 0 and float(best.get("hit_rate", 0)) >= 0.52:
            print(
                "Existe candidato a edge estatistico: pelo menos uma feature escolhida somente no treino "
                "gerou spread positivo no holdout. Nao e prova final de trade, mas e um alvo concreto "
                "para virar regra/modelo com custos, slippage e risco."
            )
        else:
            print(
                "As features novas foram auditadas, mas o holdout ainda nao mostra vantagem limpa. "
                "Neste caso a vantagem estatistica provavelmente precisa de outro dado, outro universo "
                "ou um filtro de regime mais restrito."
            )


if __name__ == "__main__":
    main()
