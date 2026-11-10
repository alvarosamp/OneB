"""Formal walk-forward validation of the BEAR-regime signal found in
scripts/regime_conditional_ic.py (annualized_volatility IC=0.082, t=4.05
— the strongest raw IC in this entire audit, see docs/data_phase_findings.md
finding #10).

A strong pooled IC is necessary but not sufficient — every previous
"promising" result in this audit (cross-sectional volatility, triple-
barrier risk, regime-transition detection) looked good on one metric and
then failed a proper out-of-sample test. This applies the same bar here:

  1. Label is a same-day CROSS-SECTIONAL rank (top half of that day's
     5-day forward return), not an absolute threshold — matches what the
     IC actually measured (Spearman rank correlation), rather than
     switching to a different, weaker formulation already rejected
     earlier in this audit (see label_horizon_scan.py).
  2. Train/holdout split is walk-forward over BEAR-labeled dates only,
     using scripts/research_folds.date_based_folds (date-based, not
     row_index — see finding on why that matters once history spans
     more than one regime).
  3. Reports AUC, accuracy vs baseline, Brier — same discipline as every
     other experiment here. A holdout AUC that doesn't clear baseline
     kills the "solid IC" reading, exactly like it did for the
     regime-transition experiment's circular AUC=0.874.

Run: MARKET_HISTORY_PERIOD=5y python -m scripts.regime_conditional_validation
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app import probability_model as pm
from scripts.compare_recommendations import DEFAULT_SYMBOLS, _load_prepared, _symbols
from scripts.cross_sectional_ic import _build_panel
from scripts.regime_conditional_ic import BEAR_THRESHOLD, _label, _market_regime_by_date
from scripts.research_folds import date_based_folds

pd.set_option("display.width", 140)

FOLDS = 4
EMBARGO_DAYS = 10
FEATURES = ["annualized_volatility", "atr_pct"]


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


def _add_cross_sectional_label(panel: pd.DataFrame) -> pd.DataFrame:
    """label=1 if this row's forward return is above the MEDIAN of that
    same calendar day's cross-section — mirrors what the Spearman IC in
    regime_conditional_ic.py actually measured (relative rank, not an
    absolute return threshold)."""
    panel = panel.copy()
    daily_median = panel.groupby("date")["fwd_return_5d"].transform("median")
    panel["label"] = (panel["fwd_return_5d"] > daily_median).astype(int)
    return panel


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
    panel = _add_cross_sectional_label(panel)

    bear = panel[panel["regime"] == "BEAR"].copy()
    n_days = bear["date"].nunique()
    print(f"Amostras em regime BEAR: {len(bear)} | dias unicos: {n_days}")
    print(f"P(label=1, acima da mediana do dia) = {bear['label'].mean():.4f} (deveria ficar perto de 0.5 por construcao)\n")

    folds = date_based_folds(bear["date"], FOLDS, window_days=n_days, embargo_days=EMBARGO_DAYS)
    if len(folds) < 2:
        raise SystemExit("Dias insuficientes em regime BEAR para separar treino + holdout.")
    *train_folds, holdout_fold = folds
    print(f"Folds (datas): {[(str(s.date()), str(e.date())) for s, e in folds]}")
    print(f"Holdout: {holdout_fold[0].date()} a {holdout_fold[1].date()}\n")

    def _rows(start, end) -> pd.DataFrame:
        return bear[(bear["date"] >= start) & (bear["date"] < end)]

    train_df = pd.concat([_rows(*f) for f in train_folds])
    holdout_df = _rows(*holdout_fold)

    train_x = train_df[FEATURES].to_numpy(dtype=float)
    train_y = train_df["label"].to_numpy(dtype=float)
    model = pm.fit(FEATURES, train_x.tolist(), train_y.tolist())

    holdout_x = holdout_df[FEATURES].to_numpy(dtype=float)
    holdout_y = holdout_df["label"].to_numpy(dtype=float)
    holdout_probs = np.array([pm.predict_proba(model, row.tolist()) for row in holdout_x])

    baseline = max(holdout_y.mean(), 1 - holdout_y.mean()) if len(holdout_y) else None
    accuracy = float(((holdout_probs >= 0.5).astype(float) == holdout_y).mean()) if len(holdout_y) else None
    auc = _auc(holdout_y, holdout_probs)

    print("=" * 90)
    print("HOLDOUT (fold mais recente de dias BEAR, nunca usado no treino)")
    print("=" * 90)
    print(f"n_train={len(train_df)} | n_holdout={len(holdout_df)}")
    print(f"holdout_baseline_accuracy = {round(baseline, 4) if baseline is not None else None}")
    print(f"holdout_accuracy          = {round(accuracy, 4) if accuracy is not None else None}")
    print(f"holdout_auc               = {round(auc, 4) if auc is not None else None}  (0.50 = sem poder preditivo)")
    print(f"holdout_brier             = {round(_brier(holdout_y, holdout_probs), 4)}")

    print("\n" + "=" * 90)
    print("VEREDITO")
    print("=" * 90)
    if auc is not None and accuracy is not None and baseline is not None and auc > 0.55 and accuracy > baseline:
        print(
            "-> O sinal SOBREVIVEU ao holdout: AUC > 0.55 e accuracy acima do baseline, treinado\n"
            "e testado inteiramente dentro de dias de regime BEAR. Esse e o primeiro resultado de\n"
            "toda a auditoria a passar nesse teste. Ainda vale: (a) confirmar em mais janelas BEAR\n"
            "conforme mais historico ficar disponivel (so tivemos ~372 dias BEAR em 5 anos), e (b)\n"
            "so acoplar ao decision_engine com um gate explicito de deteccao de regime, nunca como\n"
            "sinal unico."
        )
    else:
        print(
            "-> Mesmo o IC mais forte da sessao (t=4.05) NAO sobreviveu ao holdout walk-forward.\n"
            "Confirma o padrao de todos os experimentos anteriores: correlacao agregada forte nao\n"
            "implica modelo treinavel/generalizavel. Nao promover para producao."
        )


if __name__ == "__main__":
    main()
