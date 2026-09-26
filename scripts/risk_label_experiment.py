"""Reformulates the Signal Quality problem as risk prediction instead of
direction prediction: "will this trade hit its STOP before its TARGET?"
instead of "will the price go up?".

Rationale (see conversation/session notes): volatility and path-dependent
risk outcomes are structurally more autocorrelated and predictable than
raw price direction — a well-established empirical regularity (volatility
clustering) — and this framing feeds directly into a risk filter/position
sizing role rather than an alpha-generation role, which is a more
defensible use of a weak model.

Labeling method: triple-barrier (López de Prado, "Advances in Financial
Machine Learning", ch. 3) — already the methodological lineage this repo
uses (see scripts/calibrate_decision_strategy.py's embargo/purging, which
cites the same author). Three barriers per sample:
  - upper barrier  = entry + TARGET_ATR_MULTIPLIER * ATR  (take-profit)
  - lower barrier   = entry - STOP_ATR_MULTIPLIER * ATR    (stop-loss)
  - vertical barrier = HORIZON_DAYS trading days out        (time limit)
Whichever is touched first decides the label. Same-day double-touch is
resolved conservatively (stop wins — can't assume the best-case fill
order intraday from daily OHLC). Samples that hit neither barrier within
the horizon are DROPPED, not labeled 0 — an unresolved trade is not
evidence of a winning trade.

Same validation discipline as the rest of this audit: features->label
correlation on train fold only, walk-forward train/holdout split
(identical folds to scripts/train_probability_model.py), then a temporal
stability check (first half vs second half) — the check that killed the
cross-sectional volatility signal in the prior experiment. Nothing here
gets promoted to production without passing all of it.

Run: python -m scripts.risk_label_experiment
"""
from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

from app import paper_simulator as sim
from app import probability_model as pm
from scripts.calibrate_decision_strategy import EMBARGO_DAYS, WALK_FORWARD_FOLDS, WALK_FORWARD_WINDOW_DAYS
from scripts.compare_recommendations import DEFAULT_SYMBOLS, _load_prepared, _symbols
from scripts.research_folds import date_based_folds

pd.set_option("display.width", 140)

HORIZON_DAYS = 15  # vertical barrier — max holding period considered
STOP_MULT = sim.STOP_ATR_MULTIPLIER
TARGET_MULT = sim.TARGET_ATR_MULTIPLIER
ALPHA = 0.05


def _triple_barrier_label(history: pd.DataFrame, i: int, atr: float, horizon: int) -> int | None:
    """1 = stop hit first (bad trade), 0 = target hit first (good trade),
    None = neither barrier touched within `horizon` (unresolved, dropped).
    """
    entry = float(history["close"].iloc[i])
    stop_level = entry - STOP_MULT * atr
    target_level = entry + TARGET_MULT * atr

    highs = history["high"].values
    lows = history["low"].values
    end = min(i + 1 + horizon, len(history))
    for j in range(i + 1, end):
        hit_stop = lows[j] <= stop_level
        hit_target = highs[j] >= target_level
        if hit_stop:
            return 1
        if hit_target:
            return 0
    return None


def _build_dataset(prepared: dict, benchmark: dict | None) -> pd.DataFrame:
    rows = []
    for symbol, data in prepared.items():
        history = data["history"]
        atr = data["atr"]
        limit = len(history) - HORIZON_DAYS
        for i in range(0, limit):
            features = sim.feature_vector(data, i, benchmark)
            if features is None:
                continue
            atr_i = float(atr.iloc[i])
            if pd.isna(atr_i) or atr_i <= 0:
                continue
            label = _triple_barrier_label(history, i, atr_i, HORIZON_DAYS)
            if label is None:
                continue
            row = {"symbol": symbol, "date": history.index[i].normalize(), "label": label}
            row.update(dict(zip(sim.FEATURE_NAMES, features)))
            rows.append(row)
    return pd.DataFrame(rows)


def _fisher_z_pvalue(r: float, n: int) -> float | None:
    if n < 4 or abs(r) >= 1:
        return None
    z = math.atanh(r) * math.sqrt(n - 3)
    return 2 * (1 - NormalDist().cdf(abs(z)))


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


def _fit_eval(df: pd.DataFrame, train_folds: list[tuple], holdout_fold: tuple) -> dict:
    def _rows_in_range(start, end) -> pd.DataFrame:
        return df[(df["date"] >= start) & (df["date"] < end)]

    train_df = pd.concat([_rows_in_range(*fold) for fold in train_folds])
    holdout_df = _rows_in_range(*holdout_fold)
    if train_df.empty or holdout_df.empty:
        return {"n_train": len(train_df), "n_holdout": len(holdout_df)}

    train_x = train_df[sim.FEATURE_NAMES].to_numpy(dtype=float)
    train_y = train_df["label"].to_numpy(dtype=float)
    model = pm.fit(sim.FEATURE_NAMES, train_x.tolist(), train_y.tolist())

    holdout_x = holdout_df[sim.FEATURE_NAMES].to_numpy(dtype=float)
    holdout_y = holdout_df["label"].to_numpy(dtype=float)
    holdout_probs = np.array([pm.predict_proba(model, row.tolist()) for row in holdout_x])

    baseline = max(holdout_y.mean(), 1 - holdout_y.mean())
    accuracy = float(((holdout_probs >= 0.5).astype(float) == holdout_y).mean())
    auc = _auc(holdout_y, holdout_probs)

    return {
        "n_train": len(train_df),
        "n_holdout": len(holdout_df),
        "holdout_stop_rate": round(float(holdout_y.mean()), 4),
        "holdout_baseline_accuracy": round(float(baseline), 4),
        "holdout_accuracy": round(accuracy, 4),
        "holdout_auc": round(auc, 4) if auc is not None else None,
        "holdout_brier": round(_brier(holdout_y, holdout_probs), 4),
    }


def main() -> None:
    symbols = _symbols() or DEFAULT_SYMBOLS
    prepared, benchmark, skipped = _load_prepared(symbols)
    if not prepared:
        raise SystemExit("Nenhum simbolo com historico suficiente.")

    df = _build_dataset(prepared, benchmark)
    print(f"Simbolos: {len(prepared)} | Horizonte: {HORIZON_DAYS}d | Stop={STOP_MULT}xATR | Target={TARGET_MULT}xATR")
    print(f"Amostras resolvidas (bateram stop OU alvo dentro do horizonte): {len(df)}")

    folds = date_based_folds(df["date"], WALK_FORWARD_FOLDS, WALK_FORWARD_WINDOW_DAYS, EMBARGO_DAYS)
    if len(folds) < 2:
        raise SystemExit("Historico insuficiente.")
    *train_folds, holdout_fold = folds

    # --- Passo 1: balanceamento + correlacao no treino ---
    train_only = pd.concat([df[(df["date"] >= s) & (df["date"] < e)] for s, e in train_folds])
    n_train = len(train_only)
    stop_rate = train_only["label"].mean()

    print("\n" + "=" * 90)
    print("PASSO 1 — Balanceamento e correlacao no TREINO")
    print("=" * 90)
    print(f"P(stop antes do alvo) no treino = {stop_rate:.4f} | baseline = {max(stop_rate, 1 - stop_rate):.4f}")
    bonferroni_alpha = ALPHA / len(sim.FEATURE_NAMES)
    rows = []
    for name in sim.FEATURE_NAMES:
        r = float(train_only[name].corr(train_only["label"]))
        p = _fisher_z_pvalue(r, n_train)
        rows.append(
            {
                "feature": name,
                "pearson_r": round(r, 4),
                "p_value": round(p, 5) if p is not None else None,
                "significativo_bonferroni": (p is not None) and (p < bonferroni_alpha),
            }
        )
    corr_df = pd.DataFrame(rows).sort_values("pearson_r", key=lambda s: s.abs(), ascending=False)
    print(corr_df.to_string(index=False))

    # --- Passo 2: walk-forward holdout (nunca tocado ate aqui) ---
    print("\n" + "=" * 90)
    print("PASSO 2 — Holdout walk-forward (protocolo identico ao train_probability_model.py)")
    print("=" * 90)
    result = _fit_eval(df, train_folds, holdout_fold)
    for k, v in result.items():
        print(f"  {k}: {v}")

    # --- Passo 3: estabilidade temporal (o teste que matou o experimento anterior) ---
    print("\n" + "=" * 90)
    print("PASSO 3 — Estabilidade temporal (primeira metade vs segunda metade)")
    print("=" * 90)
    days = sorted(df["date"].unique())
    midpoint = days[len(days) // 2]
    for label, sub in [("Primeira metade", df[df["date"] < midpoint]), ("Segunda metade", df[df["date"] >= midpoint])]:
        stop_rate_half = sub["label"].mean()
        best_row = sub[sim.FEATURE_NAMES].corrwith(sub["label"]).abs().idxmax()
        best_corr = float(sub[best_row].corr(sub["label"]))
        p = _fisher_z_pvalue(best_corr, len(sub))
        print(
            f"  {label} (n={len(sub)}): P(stop)={stop_rate_half:.3f} | melhor feature='{best_row}' "
            f"r={best_corr:.4f} p={p:.5f}" if p is not None else f"  {label}: n insuficiente"
        )

    print("\n" + "=" * 90)
    print("VEREDITO")
    print("=" * 90)
    auc = result.get("holdout_auc")
    acc = result.get("holdout_accuracy")
    baseline = result.get("holdout_baseline_accuracy")
    if auc is not None and acc is not None and baseline is not None and auc > 0.55 and acc > baseline:
        print(
            "-> AUC no holdout > 0.55 e accuracy acima do baseline: candidato real. Ainda assim, só "
            "promover para producao depois de confirmar estabilidade temporal (Passo 3) em uma janela "
            "mais longa que 2 anos — a mesma cautela que derrubou o experimento cross-sectional anterior."
        )
    else:
        print(
            "-> Sem melhora convincente sobre o baseline no holdout. A reformulacao do alvo (risco em vez "
            "de direcao) nao resolveu sozinha o problema de fundo: as 11 features atuais parecem ter teto "
            "de informacao independente do que se pergunta a elas. Isso aponta mais forte ainda para a "
            "necessidade de dado de natureza diferente (fundamentals, order flow, sentimento), nao apenas "
            "reformulacao do alvo ou do modelo."
        )


if __name__ == "__main__":
    main()
