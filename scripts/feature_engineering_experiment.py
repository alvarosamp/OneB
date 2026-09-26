"""Formal A/B test: does adding regime/cross-asset/lag features improve the
Signal Quality model over the current 11 features?

Methodology (kept deliberately strict, same standard as
scripts/calibrate_decision_strategy.py):

  1. Candidate features are proposed from domain reasoning (regime strength,
     cross-asset context, momentum-of-momentum), not by mining for whatever
     correlates — mining first and validating on the same data is how you
     manufacture a false edge.
  2. Correlation with the label is computed ONLY on the training folds.
     The holdout fold is never touched until both models are already fitted
     — looking at holdout correlations before choosing features is
     information leakage, just slower.
  3. Two models are trained with the IDENTICAL walk-forward
     train/holdout split used in scripts/train_probability_model.py:
       Model A — the 11 features already in production
       Model B — those 11 + the new candidates
     Both are evaluated on the same untouched holdout fold.
  4. Reported metrics: accuracy vs baseline (majority class), ROC-AUC,
     Brier score — not accuracy alone (see EDA lesson on the accuracy trap).
  5. Correlation significance uses the Fisher z-transform (exact for Pearson
     r under normality assumptions, standard library only — see
     statistics.NormalDist), with a Bonferroni-corrected threshold since
     multiple features are tested at once.

Run: python -m scripts.feature_engineering_experiment
"""
from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

from app import indicators
from app import paper_simulator as sim
from app import probability_model as pm
from app.market_data import macro_data
from scripts.calibrate_decision_strategy import EMBARGO_DAYS, WALK_FORWARD_FOLDS, WALK_FORWARD_WINDOW_DAYS
from scripts.compare_recommendations import DEFAULT_SYMBOLS, _load_prepared, _symbols
from scripts.research_folds import date_based_folds

pd.set_option("display.width", 140)

NEW_FEATURE_NAMES = [
    "adx14",
    "di_diff",
    "ema20_50_gap_pct",
    "rsi_lag3",
    "rsi_momentum_3d",
    "macd_hist_slope_3d",
    "dxy_return_5d",
    "us10y_change_5d",
]

LABEL_HORIZON_DAYS = 5
LABEL_THRESHOLD_PCT = 0.5
ALPHA = 0.05  # significance level before Bonferroni correction


# ---------------------------------------------------------------------------
# Cross-asset alignment (FRED daily series -> each equity's trading calendar)
# ---------------------------------------------------------------------------
def _naive_date_index(series: pd.Series) -> pd.Series:
    idx = pd.to_datetime(series.index)
    if idx.tz is not None:
        idx = idx.tz_convert(None)
    idx = idx.normalize()
    out = series.copy()
    out.index = idx
    return out[~out.index.duplicated(keep="last")]


def _load_macro_aligned(equity_index: pd.DatetimeIndex) -> dict[str, pd.Series]:
    naive_equity_index = pd.to_datetime(equity_index)
    if naive_equity_index.tz is not None:
        naive_equity_index = naive_equity_index.tz_convert(None)
    naive_equity_index = naive_equity_index.normalize()

    aligned = {}
    for key in ("DXY", "US10Y"):
        history = macro_data.get_macro_history(key)
        close = _naive_date_index(history["close"]) if not history.empty else pd.Series(dtype=float)
        aligned[key] = close.reindex(naive_equity_index, method="ffill")
        aligned[key].index = equity_index  # restore original (possibly tz-aware) index for row-aligned lookup
    return aligned


# ---------------------------------------------------------------------------
# New candidate features, per symbol (vectorized once, then indexed per row)
# ---------------------------------------------------------------------------
def _extra_series(history: pd.DataFrame, data: dict, dxy_aligned: pd.Series, us10y_aligned: pd.Series) -> dict:
    close, high, low = history["close"], history["high"], history["low"]
    adx_df = indicators.adx(high, low, close, 14)
    ema20 = indicators.ema(close, 20)
    ema50 = indicators.ema(close, 50)
    rsi = data["rsi"]
    macd_hist = data["macd"]["histogram"]
    return {
        "adx14": adx_df["adx"],
        "di_diff": adx_df["plus_di"] - adx_df["minus_di"],
        "ema20_50_gap_pct": (ema20 - ema50) / close * 100,
        "rsi_lag3": rsi.shift(3),
        "rsi_momentum_3d": rsi - rsi.shift(3),
        "macd_hist_slope_3d": macd_hist - macd_hist.shift(3),
        "dxy_return_5d": dxy_aligned.pct_change(5) * 100,
        "us10y_change_5d": us10y_aligned.diff(5),
    }


def _build_dataset(prepared: dict, benchmark: dict | None) -> pd.DataFrame:
    rows = []
    for symbol, data in prepared.items():
        history = data["history"]
        macro_aligned = _load_macro_aligned(history.index)
        extra = _extra_series(history, data, macro_aligned["DXY"], macro_aligned["US10Y"])

        limit = len(history) - LABEL_HORIZON_DAYS
        for i in range(0, limit):
            base_features = sim.feature_vector(data, i, benchmark)
            if base_features is None:
                continue
            new_values = [extra[name].iloc[i] for name in NEW_FEATURE_NAMES]
            if any(pd.isna(v) for v in new_values):
                continue

            price = float(history["close"].iloc[i])
            fwd_return = (float(history["close"].iloc[i + LABEL_HORIZON_DAYS]) / price - 1) * 100
            label = 1 if fwd_return > LABEL_THRESHOLD_PCT else 0

            row = {"symbol": symbol, "date": history.index[i].normalize()}
            row.update(dict(zip(sim.FEATURE_NAMES, base_features)))
            row.update(dict(zip(NEW_FEATURE_NAMES, new_values)))
            row["label"] = label
            rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Statistics helpers (standard library / numpy only — matches
# app.probability_model's "no scikit-learn/scipy" constraint)
# ---------------------------------------------------------------------------
def _fisher_z_pvalue(r: float, n: int) -> float | None:
    if n < 4 or abs(r) >= 1:
        return None
    z = math.atanh(r) * math.sqrt(n - 3)
    return 2 * (1 - NormalDist().cdf(abs(z)))


def _spearman(x: pd.Series, y: pd.Series) -> float:
    return float(x.rank().corr(y.rank()))


def _auc(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    """ROC-AUC via the rank-sum (Mann-Whitney U) identity — no scikit-learn."""
    n_pos = int(y_true.sum())
    n_neg = len(y_true) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    ranks = pd.Series(y_score).rank().to_numpy()
    sum_ranks_pos = ranks[y_true == 1].sum()
    return float((sum_ranks_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def _brier(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    return float(np.mean((y_prob - y_true) ** 2))


def _fit_eval(df: pd.DataFrame, feature_names: list[str], train_folds: list[tuple], holdout_fold: tuple) -> dict:
    def _rows_in_range(start, end) -> pd.DataFrame:
        return df[(df["date"] >= start) & (df["date"] < end)]

    train_df = pd.concat([_rows_in_range(*fold) for fold in train_folds])
    holdout_df = _rows_in_range(*holdout_fold)

    train_x = train_df[feature_names].to_numpy(dtype=float)
    train_y = train_df["label"].to_numpy(dtype=float)
    model = pm.fit(feature_names, train_x.tolist(), train_y.tolist())

    holdout_x = holdout_df[feature_names].to_numpy(dtype=float)
    holdout_y = holdout_df["label"].to_numpy(dtype=float)
    holdout_probs = np.array([pm.predict_proba(model, row.tolist()) for row in holdout_x])

    baseline = max(holdout_y.mean(), 1 - holdout_y.mean()) if len(holdout_y) else None
    accuracy = float(((holdout_probs >= 0.5).astype(float) == holdout_y).mean()) if len(holdout_y) else None

    return {
        "n_train": len(train_df),
        "n_holdout": len(holdout_df),
        "holdout_baseline_accuracy": round(float(baseline), 4) if baseline is not None else None,
        "holdout_accuracy": round(accuracy, 4) if accuracy is not None else None,
        "holdout_auc": round(_auc(holdout_y, holdout_probs), 4) if _auc(holdout_y, holdout_probs) is not None else None,
        "holdout_brier": round(_brier(holdout_y, holdout_probs), 4) if len(holdout_y) else None,
    }


def main() -> None:
    symbols = _symbols() or DEFAULT_SYMBOLS
    prepared, benchmark, skipped = _load_prepared(symbols)
    if not prepared:
        raise SystemExit("Nenhum simbolo com historico suficiente.")

    df = _build_dataset(prepared, benchmark)
    folds = date_based_folds(df["date"], WALK_FORWARD_FOLDS, WALK_FORWARD_WINDOW_DAYS, EMBARGO_DAYS)
    if len(folds) < 2:
        raise SystemExit("Historico insuficiente para separar treino + holdout.")
    *train_folds, holdout_fold = folds

    print(f"Amostras totais (com as {len(NEW_FEATURE_NAMES)} novas features validas): {len(df)}")
    print(f"Folds de treino: {train_folds} | Fold de holdout: {holdout_fold}\n")

    # --- Passo 2: correlacao das novas features com o label, SO no treino ---
    train_only = pd.concat(
        [df[(df["date"] >= s) & (df["date"] < e)] for s, e in train_folds]
    )
    n_train = len(train_only)
    bonferroni_alpha = ALPHA / len(NEW_FEATURE_NAMES)

    print("=" * 90)
    print("PASSO 1 — Correlacao das NOVAS features com o label (apenas fold de TREINO)")
    print("=" * 90)
    print(f"n={n_train} | alpha={ALPHA} | alpha Bonferroni (corrigido p/ {len(NEW_FEATURE_NAMES)} testes)={bonferroni_alpha:.5f}\n")

    corr_rows = []
    for name in NEW_FEATURE_NAMES:
        pearson_r = float(train_only[name].corr(train_only["label"]))
        spearman_r = _spearman(train_only[name], train_only["label"])
        p_value = _fisher_z_pvalue(pearson_r, n_train)
        corr_rows.append(
            {
                "feature": name,
                "pearson_r": round(pearson_r, 4),
                "spearman_r": round(spearman_r, 4),
                "p_value": round(p_value, 5) if p_value is not None else None,
                "significativo_bonferroni": (p_value is not None) and (p_value < bonferroni_alpha),
            }
        )
    corr_df = pd.DataFrame(corr_rows).sort_values("pearson_r", key=lambda s: s.abs(), ascending=False)
    print(corr_df.to_string(index=False))

    # --- Passo 3: treino formal A/B no MESMO split walk-forward ---
    print("\n" + "=" * 90)
    print("PASSO 2 — A/B no holdout (nunca tocado ate aqui)")
    print("=" * 90)

    result_a = _fit_eval(df, sim.FEATURE_NAMES, train_folds, holdout_fold)
    result_b = _fit_eval(df, sim.FEATURE_NAMES + NEW_FEATURE_NAMES, train_folds, holdout_fold)

    comparison = pd.DataFrame(
        [
            {"modelo": f"A — producao (11 features)", **result_a},
            {"modelo": f"B — 11 + {len(NEW_FEATURE_NAMES)} novas", **result_b},
        ]
    )
    print(comparison.to_string(index=False))

    print("\n" + "=" * 90)
    print("VEREDITO")
    print("=" * 90)
    auc_a, auc_b = result_a["holdout_auc"], result_b["holdout_auc"]
    acc_a, acc_b = result_a["holdout_accuracy"], result_b["holdout_accuracy"]
    baseline = result_b["holdout_baseline_accuracy"]
    print(f"Baseline (holdout): {baseline}")
    print(f"AUC A={auc_a} | AUC B={auc_b}  (0.50 = sem poder preditivo, 1.00 = perfeito)")
    print(f"Accuracy A={acc_a} | Accuracy B={acc_b}")
    if auc_b is not None and auc_a is not None and auc_b > auc_a + 0.02 and acc_b is not None and acc_b > baseline:
        print(
            "\n-> As novas features melhoraram o AUC de forma perceptivel E o modelo B superou o "
            "baseline no holdout. Candidato real a promover para producao (mas ainda merece re-teste "
            "em outra janela antes de qualquer retreino oficial)."
        )
    else:
        print(
            "\n-> Sem melhora convincente. Isso reforça o diagnostico do EDA anterior: o problema nao "
            "e falta dessas features especificas — e mais provavel que o teto esteja no proprio label "
            "(retorno 5d > 0.5% pode nao ser um alvo com estrutura previsivel nesses ativos/timeframe) "
            "ou em precisar de features de natureza diferente (ex: order flow, sentimento, dados que "
            "hoje nao temos). NAO promover modelo B para producao com base nisso."
        )


if __name__ == "__main__":
    main()
