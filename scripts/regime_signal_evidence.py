"""Statistical evidence report for the BEAR-regime candidate signal.

This is deliberately a research artifact, not a trading script.  It holds
out the newest BEAR-regime dates, fits models only on earlier dates, then
quantifies whether the observed AUC is distinguishable from chance.

Unlike a row bootstrap, resampling is performed by *date*.  Equities on the
same trading day share market information and are therefore not independent
observations.  The permutation test also shuffles labels within each date,
preserving the cross-sectional label balance used by this study.

Run (uses the configured market-data provider):
  MARKET_HISTORY_PERIOD=10y python -m scripts.regime_signal_evidence

The JSON output is intended to be attached to an ExperimentRecord and used
as a table source in a paper.  It must not be interpreted as approval to
trade: statistical significance and economic significance are different
questions.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from app import paper_simulator as sim
from app import probability_model as pm
from app.research_provenance import write_manifest
from scripts.compare_recommendations import DEFAULT_SYMBOLS, _load_prepared, _symbols
from scripts.cross_sectional_ic import _build_panel
from scripts.data_reliability_gate import build_report as build_data_gate
from scripts.regime_conditional_ic import _label, _market_regime_by_date
from scripts.research_folds import date_based_folds

FEATURE_SETS = {
    "volatility_atr": ["annualized_volatility", "atr_pct"],
    "volatility_only": ["annualized_volatility"],
    "atr_only": ["atr_pct"],
}


def _research_input_paths() -> list[Path]:
    """Versioned local inputs used to rebuild this exact evidence report."""
    paths = [
        Path("data/research/research_dataset_v1.csv"),
        Path("data/research/research_dataset_v1.summary.json"),
    ]
    price_cache = Path("data/raw/prices/tiingo/1d") / sim.MARKET_HISTORY_PERIOD
    if price_cache.exists():
        paths.extend(sorted(price_cache.glob("*.csv")))
        paths.extend(sorted(price_cache.glob("*.meta.json")))
    macro_cache = Path("data/raw/macro/fred")
    if macro_cache.exists():
        paths.extend(sorted(macro_cache.glob("*.csv")))
    return paths


def auc(y_true: np.ndarray, scores: np.ndarray) -> float | None:
    """Rank AUC without an additional scikit-learn dependency."""
    y_true = np.asarray(y_true, dtype=int)
    scores = np.asarray(scores, dtype=float)
    positives = int(y_true.sum())
    negatives = len(y_true) - positives
    if positives == 0 or negatives == 0:
        return None
    ranks = pd.Series(scores).rank(method="average").to_numpy()
    return float((ranks[y_true == 1].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def brier(y_true: np.ndarray, probabilities: np.ndarray) -> float:
    return float(np.mean((np.asarray(probabilities, dtype=float) - np.asarray(y_true, dtype=float)) ** 2))


def _quantiles(values: list[float], alpha: float = 0.05) -> list[float | None]:
    clean = np.asarray([value for value in values if np.isfinite(value)], dtype=float)
    if not len(clean):
        return [None, None]
    return [round(float(np.quantile(clean, alpha / 2)), 4), round(float(np.quantile(clean, 1 - alpha / 2)), 4)]


def date_block_bootstrap(
    holdout: pd.DataFrame, score_columns: list[str], iterations: int, seed: int
) -> dict[str, dict[str, list[float | None]]]:
    """Percentile CIs after resampling complete calendar-date blocks."""
    dates = holdout["date"].drop_duplicates().to_numpy()
    groups = {date: group for date, group in holdout.groupby("date", sort=False)}
    rng = np.random.default_rng(seed)
    samples = {column: {"auc": [], "brier": []} for column in score_columns}
    for _ in range(iterations):
        sampled_dates = rng.choice(dates, size=len(dates), replace=True)
        sample = pd.concat([groups[date] for date in sampled_dates], ignore_index=True)
        y = sample["label"].to_numpy(dtype=int)
        for column in score_columns:
            samples[column]["auc"].append(auc(y, sample[column].to_numpy(dtype=float)))
            samples[column]["brier"].append(brier(y, sample[column].to_numpy(dtype=float)))
    return {
        column: {metric: _quantiles(values) for metric, values in metrics.items()}
        for column, metrics in samples.items()
    }


def within_date_permutation_pvalue(
    holdout: pd.DataFrame, score_column: str, iterations: int, seed: int
) -> float | None:
    """One-sided AUC p-value under no within-date association with the score."""
    observed = auc(holdout["label"].to_numpy(dtype=int), holdout[score_column].to_numpy(dtype=float))
    if observed is None:
        return None
    rng = np.random.default_rng(seed)
    null_aucs: list[float] = []
    for _ in range(iterations):
        shuffled = []
        for _, group in holdout.groupby("date", sort=False):
            shuffled.extend(rng.permutation(group["label"].to_numpy(dtype=int)))
        value = auc(np.asarray(shuffled), holdout[score_column].to_numpy(dtype=float))
        if value is not None:
            null_aucs.append(value)
    return round((1 + sum(value >= observed for value in null_aucs)) / (len(null_aucs) + 1), 4)


def _add_label_and_regime(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.copy()
    regime_by_date = _market_regime_by_date()
    dates = pd.to_datetime(panel["date"])
    dates = dates.dt.tz_localize(None) if dates.dt.tz is not None else dates
    panel["date"] = dates.dt.normalize()
    panel["regime"] = panel["date"].map(lambda date: _label(regime_by_date.get(date)))
    daily_median = panel.groupby("date")["fwd_return_5d"].transform("median")
    panel["label"] = (panel["fwd_return_5d"] > daily_median).astype(int)
    return panel


def _fit_scores(train: pd.DataFrame, holdout: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    holdout = holdout.copy()
    models = {}
    for name, features in FEATURE_SETS.items():
        model = pm.fit(features, train[features].to_numpy(dtype=float).tolist(), train["label"].tolist())
        holdout[name] = [pm.predict_proba(model, row) for row in holdout[features].to_numpy(dtype=float)]
        models[name] = {"features": features, "train_accuracy": model["train_accuracy"]}
    base_rate = float(train["label"].mean())
    holdout["train_prevalence"] = base_rate
    return holdout, {"models": models, "train_prevalence": round(base_rate, 4)}


def run_evidence_report(
    bootstrap_iterations: int = 2000, permutations: int = 2000, seed: int = 20260821, symbols: list[str] | None = None, universe_id: str = "oneb_default_24"
) -> dict:
    data_gate = build_data_gate()
    if data_gate["status"] != "PASS":
        raise RuntimeError(f"Pesquisa bloqueada pelo data gate: {data_gate['failure_count']} falha(s).")
    requested_symbols = symbols or _symbols() or DEFAULT_SYMBOLS
    prepared, benchmark, skipped = _load_prepared(requested_symbols)
    if not prepared:
        raise RuntimeError("Nenhum símbolo com histórico suficiente.")
    bear = _add_label_and_regime(_build_panel(prepared, benchmark))
    bear = bear[bear["regime"] == "BEAR"].copy()
    needed = list({feature for features in FEATURE_SETS.values() for feature in features})
    bear = bear.replace([np.inf, -np.inf], np.nan).dropna(subset=needed + ["label"])
    unique_days = bear["date"].nunique()
    folds = date_based_folds(bear["date"], num_folds=4, window_days=unique_days, embargo_days=10)
    if len(folds) < 2:
        raise RuntimeError("Dias BEAR insuficientes para treino e holdout temporal.")
    *training_folds, holdout_fold = folds

    def rows(interval: tuple[pd.Timestamp, pd.Timestamp]) -> pd.DataFrame:
        return bear[(bear["date"] >= interval[0]) & (bear["date"] < interval[1])]

    train = pd.concat([rows(interval) for interval in training_folds], ignore_index=True)
    holdout = rows(holdout_fold).reset_index(drop=True)
    if train.empty or holdout.empty or train["label"].nunique() < 2 or holdout["label"].nunique() < 2:
        raise RuntimeError("Treino ou holdout não contém as duas classes necessárias.")
    holdout, model_info = _fit_scores(train, holdout)
    score_columns = list(FEATURE_SETS) + ["train_prevalence"]
    bootstrap = date_block_bootstrap(holdout, score_columns, bootstrap_iterations, seed)
    metrics = {}
    y = holdout["label"].to_numpy(dtype=int)
    for column in score_columns:
        probabilities = holdout[column].to_numpy(dtype=float)
        metrics[column] = {"auc": round(auc(y, probabilities), 4), "brier": round(brier(y, probabilities), 4), "ci_95": bootstrap[column]}
    primary = "volatility_atr"
    metrics[primary]["within_date_permutation_p_value"] = within_date_permutation_pvalue(holdout, primary, permutations, seed + 1)
    metrics[primary]["auc_gain_over_volatility_only"] = round(metrics[primary]["auc"] - metrics["volatility_only"]["auc"], 4)
    return {
        "study": "BEAR-regime cross-sectional 5-day ranking signal",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "RESEARCH_ONLY",
        "data_gate": {"status": data_gate["status"], "generated_at": data_gate["generated_at"], "failure_count": data_gate["failure_count"]},
        "protocol": {
            "holdout": "most recent date-based BEAR fold; earlier folds only used for fitting",
            "label": "above same-date median of 5-day forward return",
            "bootstrap": {"unit": "calendar date block", "iterations": bootstrap_iterations, "seed": seed},
            "permutation": {"scheme": "labels shuffled within calendar date", "iterations": permutations, "seed": seed + 1},
        },
        "universe": {"universe_id": universe_id, "requested_symbols": requested_symbols, "used_symbols": sorted(prepared), "skipped_symbols": skipped},
        "data": {
            "equity_providers": sorted({str(data["history"].attrs.get("provider", "unknown")) for data in prepared.values()}),
            "market_history_period": sim.MARKET_HISTORY_PERIOD,
            "input_files": [str(path) for path in _research_input_paths() if path.exists()],
        },
        "sample": {
            "bear_days": int(unique_days), "train_rows": int(len(train)), "holdout_rows": int(len(holdout)),
            "holdout_days": int(holdout["date"].nunique()), "train_period": [str(train["date"].min().date()), str(train["date"].max().date())],
            "holdout_period": [str(holdout["date"].min().date()), str(holdout["date"].max().date())],
        },
        "models": model_info,
        "metrics": metrics,
        "interpretation": "Statistical evidence only. AUC above 0.50 does not establish tradable economic value; assess fees, turnover, drawdown, and external-universe replication separately.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a date-block statistical evidence report for the BEAR signal.")
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--permutations", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260821)
    parser.add_argument("--output", type=Path, default=Path("data/research/regime_signal_evidence.json"))
    parser.add_argument("--symbols", default="", help="Comma-separated independent universe for replication.")
    parser.add_argument("--universe-id", default="oneb_default_24", help="Immutable identifier for the evaluated universe.")
    args = parser.parse_args()
    if args.bootstrap < 100 or args.permutations < 100:
        raise SystemExit("Use at least 100 bootstrap and permutation iterations.")
    symbols = [symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip()]
    if symbols and len(set(symbols)) < 10:
        raise SystemExit("Uma replicação cross-sectional requer ao menos 10 símbolos únicos.")
    report = run_evidence_report(args.bootstrap, args.permutations, args.seed, symbols or None, args.universe_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = write_manifest(
        args.output,
        command="python -m scripts.regime_signal_evidence",
        parameters={"bootstrap": args.bootstrap, "permutations": args.permutations, "seed": args.seed, "symbols": symbols or None, "universe_id": args.universe_id},
        input_paths=["scripts/regime_signal_evidence.py", "scripts/data_reliability_gate.py", "app/probability_model.py", *_research_input_paths()],
        data_gate=report["data_gate"],
        extra={"study": report["study"], "universe": report["universe"], "data": report["data"], "sample": report["sample"]},
    )
    print(json.dumps({"saved": str(args.output), "manifest": str(manifest), "sample": report["sample"], "metrics": report["metrics"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
