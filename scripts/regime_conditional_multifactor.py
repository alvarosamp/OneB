"""Does adding more features to the BEAR-regime model (validated at
AUC~0.53 in scripts/regime_conditional_validation.py, findings #11/#12)
push it higher than annualized_volatility + atr_pct alone?

scripts/feature_engineering_experiment.py already tested cross-asset/lag
features (DXY, US10Y, RSI momentum, MACD slope) and found they made the
POOLED model worse (AUC 0.475 -> 0.452). But that test pooled BULL+BEAR+
NEUTRO together — exactly the mistake findings #10-#12 showed cancels
opposite-signed regime effects. This re-tests the same candidate features,
restricted to BEAR days only, with the same walk-forward-in-regime
protocol as regime_conditional_validation.py.

Model A: annualized_volatility + atr_pct (the validated baseline, AUC~0.53)
Model B: A + rsi, trend, score, dxy_return_5d, us10y_change_5d
         (rsi/trend/score showed NEGATIVE IC in BEAR in finding #10 — a
         real signal used backwards is still useful to a model, unlike a
         pooled test where the sign flips per-regime and cancels out)

Run: MARKET_HISTORY_PERIOD=10y python -m scripts.regime_conditional_multifactor
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app import paper_simulator as sim
from app import probability_model as pm
from scripts.compare_recommendations import DEFAULT_SYMBOLS, _load_prepared, _symbols
from scripts.cross_sectional_ic import _build_panel
from scripts.feature_engineering_experiment import _load_macro_aligned
from scripts.regime_conditional_ic import _label, _market_regime_by_date
from scripts.research_folds import date_based_folds

pd.set_option("display.width", 140)

FOLDS = 4
EMBARGO_DAYS = 10
MODEL_A_FEATURES = ["annualized_volatility", "atr_pct"]
MODEL_B_EXTRA = ["rsi", "trend", "score", "dxy_return_5d", "us10y_change_5d"]
MODEL_B_FEATURES = MODEL_A_FEATURES + MODEL_B_EXTRA


def _auc(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    n_pos = int(y_true.sum())
    n_neg = len(y_true) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    ranks = pd.Series(y_score).rank().to_numpy()
    sum_ranks_pos = ranks[y_true == 1].sum()
    return float((sum_ranks_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def _brier(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    return float(np.mean((y_prob - y_true) ** 2))


def _add_macro_features(prepared: dict, panel: pd.DataFrame) -> pd.DataFrame:
    """Attaches dxy_return_5d / us10y_change_5d per (symbol, date), reusing
    the same aligned-macro-series logic already validated in
    scripts/feature_engineering_experiment.py."""
    frames = []
    for symbol, data in prepared.items():
        history = data["history"]
        macro = _load_macro_aligned(history.index)
        dxy_return_5d = macro["DXY"].pct_change(5) * 100
        us10y_change_5d = macro["US10Y"].diff(5)
        idx = history.index
        naive_idx = idx.tz_localize(None) if idx.tz is not None else idx
        frame = pd.DataFrame(
            {
                "symbol": symbol,
                "date": naive_idx.normalize(),
                "dxy_return_5d": dxy_return_5d.to_numpy(),
                "us10y_change_5d": us10y_change_5d.to_numpy(),
            }
        )
        frames.append(frame)
    macro_df = pd.concat(frames, ignore_index=True)
    return panel.merge(macro_df, on=["symbol", "date"], how="left")


def _fit_eval(bear: pd.DataFrame, features: list[str], train_folds, holdout_fold) -> dict:
    def _rows(start, end) -> pd.DataFrame:
        return bear[(bear["date"] >= start) & (bear["date"] < end)]

    train_df = pd.concat([_rows(*f) for f in train_folds]).dropna(subset=features)
    holdout_df = _rows(*holdout_fold).dropna(subset=features)

    train_x = train_df[features].to_numpy(dtype=float)
    train_y = train_df["label"].to_numpy(dtype=float)
    model = pm.fit(features, train_x.tolist(), train_y.tolist())

    holdout_x = holdout_df[features].to_numpy(dtype=float)
    holdout_y = holdout_df["label"].to_numpy(dtype=float)
    holdout_probs = np.array([pm.predict_proba(model, row.tolist()) for row in holdout_x])

    baseline = max(holdout_y.mean(), 1 - holdout_y.mean()) if len(holdout_y) else None
    accuracy = float(((holdout_probs >= 0.5).astype(float) == holdout_y).mean()) if len(holdout_y) else None
    return {
        "n_train": len(train_df),
        "n_holdout": len(holdout_df),
        "holdout_baseline_accuracy": round(baseline, 4) if baseline is not None else None,
        "holdout_accuracy": round(accuracy, 4) if accuracy is not None else None,
        "holdout_auc": round(_auc(holdout_y, holdout_probs), 4) if _auc(holdout_y, holdout_probs) is not None else None,
        "holdout_brier": round(_brier(holdout_y, holdout_probs), 4) if len(holdout_y) else None,
    }


def main() -> None:
    symbols = _symbols() or DEFAULT_SYMBOLS
    prepared, benchmark, skipped = _load_prepared(symbols)
    if not prepared:
        raise SystemExit("Nenhum simbolo com historico suficiente.")

    panel = _build_panel(prepared, benchmark)
    market_regime = _market_regime_by_date()
    naive_dates = panel["date"].dt.tz_localize(None) if panel["date"].dt.tz is not None else panel["date"]
    panel["regime"] = naive_dates.map(lambda d: _label(market_regime.get(d)))
    panel["date"] = naive_dates
    panel = _add_macro_features(prepared, panel)

    daily_median = panel.groupby("date")["fwd_return_5d"].transform("median")
    panel["label"] = (panel["fwd_return_5d"] > daily_median).astype(int)

    bear = panel[panel["regime"] == "BEAR"].copy()
    n_days = bear["date"].nunique()
    print(f"Amostras BEAR: {len(bear)} | dias unicos: {n_days}")

    folds = date_based_folds(bear["date"], FOLDS, window_days=n_days, embargo_days=EMBARGO_DAYS)
    if len(folds) < 2:
        raise SystemExit("Dias insuficientes em regime BEAR.")
    *train_folds, holdout_fold = folds
    print(f"Holdout: {holdout_fold[0].date()} a {holdout_fold[1].date()}\n")

    result_a = _fit_eval(bear, MODEL_A_FEATURES, train_folds, holdout_fold)
    result_b = _fit_eval(bear, MODEL_B_FEATURES, train_folds, holdout_fold)

    comparison = pd.DataFrame(
        [
            {"modelo": f"A — validado ({', '.join(MODEL_A_FEATURES)})", **result_a},
            {"modelo": f"B — A + {', '.join(MODEL_B_EXTRA)}", **result_b},
        ]
    )
    print("=" * 100)
    print("COMPARACAO — Modelo A (validado, AUC~0.53) vs Modelo B (mais features, ainda dentro de BEAR)")
    print("=" * 100)
    print(comparison.to_string(index=False))

    print("\n" + "=" * 100)
    print("VEREDITO")
    print("=" * 100)
    auc_a, auc_b = result_a["holdout_auc"], result_b["holdout_auc"]
    if auc_a is not None and auc_b is not None and auc_b > auc_a + 0.01:
        print(f"-> Modelo B melhorou (AUC {auc_a} -> {auc_b}). Combinar features condicionado ao regime certo ajuda.")
    elif auc_a is not None and auc_b is not None and auc_b < auc_a - 0.01:
        print(f"-> Modelo B piorou (AUC {auc_a} -> {auc_b}). Mais features nao ajudam mesmo dentro do regime certo — ficar com o modelo A (2 features).")
    else:
        print(f"-> Sem diferenca pratica (AUC {auc_a} vs {auc_b}). O teto do sinal BEAR parece estar mesmo em ~0.53, nao em falta de features.")


if __name__ == "__main__":
    main()
