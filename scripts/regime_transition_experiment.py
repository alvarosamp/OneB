"""Tests a different question from every prior experiment in this audit:
not "will price go up" or "will this trade hit its stop", but
"is this symbol about to flip from its current regime into a BEAR regime
in the next H days?" — i.e. correction-onset detection.

Motivation (see docs/data_phase_findings.md): scripts/regime_timeline.py
showed the 2024-2026 window isn't one clean regime, it's two sharp
corrections (Mar-Apr 2025, Feb-Mar 2026) embedded in otherwise strong
bull runs — a whipsaw pattern that is structurally hostile to
momentum/trend features (they get run over right as the correction
starts) but is exactly the pattern a REGIME-CHANGE detector is built for.

Label: using the same regime-score formula as app.regime_engine.local_regime
(vectorized per-symbol here), label=1 if the score crosses below the BEAR
threshold at any point in the next HORIZON_DAYS, given it hasn't already
crossed as of day i (rows already in a bear regime are excluded — the
question here is onset detection, not "are you currently in a
correction").

Leading features tested (all knowable at day i, no look-ahead):
  regime_score, adx, rsi, annualized_volatility, atr_pct,
  drawdown_from_20d_high, vix, vix_change_5d, dxy_return_5d,
  us10y_change_5d

Same validation discipline as every other experiment here: train-fold-only
correlation, walk-forward holdout (identical folds/protocol), and the
temporal-stability check that killed the three prior "promising" results.

Run: python -m scripts.regime_transition_experiment
"""
from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

from app import indicators
from app import probability_model as pm
from app.market_data import fred_client, macro_data
from scripts.calibrate_decision_strategy import EMBARGO_DAYS, WALK_FORWARD_FOLDS, WALK_FORWARD_WINDOW_DAYS
from scripts.compare_recommendations import DEFAULT_SYMBOLS, _load_prepared, _symbols
from scripts.research_folds import date_based_folds

pd.set_option("display.width", 140)

HORIZON_DAYS = 10
BEAR_THRESHOLD = -20.0
ALPHA = 0.05

FEATURE_NAMES = [
    "regime_score",
    "adx",
    "rsi",
    "annualized_volatility",
    "atr_pct",
    "drawdown_from_20d_high",
    "vix",
    "vix_change_5d",
    "dxy_return_5d",
    "us10y_change_5d",
]


def _naive_index(series: pd.Series) -> pd.Series:
    idx = pd.to_datetime(series.index)
    if idx.tz is not None:
        idx = idx.tz_convert(None)
    idx = idx.normalize()
    out = series.copy()
    out.index = idx
    return out[~out.index.duplicated(keep="last")]


def _regime_score(history: pd.DataFrame) -> pd.DataFrame:
    close, high, low = history["close"], history["high"], history["low"]
    ema20 = indicators.ema(close, 20)
    ema50 = indicators.ema(close, 50)
    rsi = indicators.rsi(close, 14)
    adx_df = indicators.adx(high, low, close, 14)

    trend_score = (ema20 > ema50).astype(float) * 30 - (ema20 <= ema50).astype(float) * 30
    momentum_score = (rsi - 50).clip(-35.7, 35.7) * 0.7
    score = trend_score + momentum_score
    multiplier = (adx_df["adx"] >= 25).map({True: 1.25, False: 0.7})
    score = (score * multiplier).clip(-100, 100)

    atr = indicators.atr(high, low, close, 14)
    atr_pct = atr / close * 100
    recent_high20 = close.shift(1).rolling(20, min_periods=20).max()
    drawdown = (recent_high20 - close) / recent_high20 * 100

    return pd.DataFrame(
        {
            "regime_score": score,
            "adx": adx_df["adx"],
            "rsi": rsi,
            "atr_pct": atr_pct,
            "drawdown_from_20d_high": drawdown,
            "annualized_volatility": indicators.annualized_volatility(close),
        }
    )


def _load_macro_aligned(equity_index: pd.DatetimeIndex) -> dict[str, pd.Series]:
    naive_idx = pd.to_datetime(equity_index)
    if naive_idx.tz is not None:
        naive_idx = naive_idx.tz_convert(None)
    naive_idx = naive_idx.normalize()

    vix = _naive_index(fred_client.get_series("VIXCLS")["close"]).reindex(naive_idx, method="ffill")
    dxy = _naive_index(macro_data.get_macro_history("DXY")["close"]).reindex(naive_idx, method="ffill")
    us10y = _naive_index(macro_data.get_macro_history("US10Y")["close"]).reindex(naive_idx, method="ffill")
    for series in (vix, dxy, us10y):
        series.index = equity_index
    return {"vix": vix, "dxy": dxy, "us10y": us10y}


def _build_dataset(prepared: dict) -> pd.DataFrame:
    rows = []
    for symbol, data in prepared.items():
        history = data["history"]
        regime = _regime_score(history)
        macro = _load_macro_aligned(history.index)
        vix_change_5d = macro["vix"].diff(5)
        dxy_return_5d = macro["dxy"].pct_change(5) * 100
        us10y_change_5d = macro["us10y"].diff(5)

        score = regime["regime_score"]
        limit = len(history) - HORIZON_DAYS
        for i in range(55, limit):  # 55: warm-up for EMA50/ADX, matches regime_engine's own minimum
            if pd.isna(score.iloc[i]) or score.iloc[i] <= BEAR_THRESHOLD:
                continue  # already in bear — onset detection only applies before the fact
            feature_row = {
                "regime_score": score.iloc[i],
                "adx": regime["adx"].iloc[i],
                "rsi": regime["rsi"].iloc[i],
                "annualized_volatility": regime["annualized_volatility"].iloc[i],
                "atr_pct": regime["atr_pct"].iloc[i],
                "drawdown_from_20d_high": regime["drawdown_from_20d_high"].iloc[i],
                "vix": macro["vix"].iloc[i],
                "vix_change_5d": vix_change_5d.iloc[i],
                "dxy_return_5d": dxy_return_5d.iloc[i],
                "us10y_change_5d": us10y_change_5d.iloc[i],
            }
            if any(pd.isna(v) for v in feature_row.values()):
                continue

            future_scores = score.iloc[i + 1 : i + 1 + HORIZON_DAYS]
            label = int((future_scores <= BEAR_THRESHOLD).any())

            row = {"symbol": symbol, "date": history.index[i].normalize(), "label": label}
            row.update(feature_row)
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
    def _rows(start, end) -> pd.DataFrame:
        return df[(df["date"] >= start) & (df["date"] < end)]

    train_df = pd.concat([_rows(*f) for f in train_folds])
    holdout_df = _rows(*holdout_fold)
    if train_df.empty or holdout_df.empty or train_df["label"].nunique() < 2:
        return {"n_train": len(train_df), "n_holdout": len(holdout_df), "erro": "dados insuficientes ou classe unica"}

    train_x = train_df[FEATURE_NAMES].to_numpy(dtype=float)
    train_y = train_df["label"].to_numpy(dtype=float)
    model = pm.fit(FEATURE_NAMES, train_x.tolist(), train_y.tolist())

    holdout_x = holdout_df[FEATURE_NAMES].to_numpy(dtype=float)
    holdout_y = holdout_df["label"].to_numpy(dtype=float)
    holdout_probs = np.array([pm.predict_proba(model, row.tolist()) for row in holdout_x])

    baseline = max(holdout_y.mean(), 1 - holdout_y.mean())
    accuracy = float(((holdout_probs >= 0.5).astype(float) == holdout_y).mean())
    auc = _auc(holdout_y, holdout_probs)
    return {
        "n_train": len(train_df),
        "n_holdout": len(holdout_df),
        "holdout_positive_rate": round(float(holdout_y.mean()), 4),
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

    df = _build_dataset(prepared)
    print(f"Simbolos: {len(prepared)} | Horizonte: {HORIZON_DAYS}d | Limiar BEAR: {BEAR_THRESHOLD}")
    print(f"Amostras (regime ainda nao-bear no dia i): {len(df)}")
    print(f"P(transicao para BEAR em {HORIZON_DAYS}d) = {df['label'].mean():.4f}\n")

    folds = date_based_folds(df["date"], WALK_FORWARD_FOLDS, WALK_FORWARD_WINDOW_DAYS, EMBARGO_DAYS)
    if len(folds) < 2:
        raise SystemExit("Historico insuficiente.")
    *train_folds, holdout_fold = folds

    train_only = pd.concat([df[(df["date"] >= s) & (df["date"] < e)] for s, e in train_folds])
    n_train = len(train_only)
    bonferroni_alpha = ALPHA / len(FEATURE_NAMES)

    print("=" * 90)
    print("PASSO 1 — Correlacao no TREINO")
    print("=" * 90)
    rows = []
    for name in FEATURE_NAMES:
        r = float(train_only[name].corr(train_only["label"]))
        p = _fisher_z_pvalue(r, n_train)
        rows.append({"feature": name, "pearson_r": round(r, 4), "p_value": round(p, 5) if p else None, "sig_bonferroni": p is not None and p < bonferroni_alpha})
    corr_df = pd.DataFrame(rows).sort_values("pearson_r", key=lambda s: s.abs(), ascending=False)
    print(corr_df.to_string(index=False))

    print("\n" + "=" * 90)
    print("PASSO 2 — Holdout walk-forward")
    print("=" * 90)
    result = _fit_eval(df, train_folds, holdout_fold)
    for k, v in result.items():
        print(f"  {k}: {v}")

    print("\n" + "=" * 90)
    print("PASSO 3 — Estabilidade temporal (primeira vs segunda metade)")
    print("=" * 90)
    days = sorted(df["date"].unique())
    midpoint = days[len(days) // 2]
    for label, sub in [("Primeira metade", df[df["date"] < midpoint]), ("Segunda metade", df[df["date"] >= midpoint])]:
        if sub["label"].nunique() < 2:
            print(f"  {label}: classe unica, sem correlacao definida")
            continue
        best = sub[FEATURE_NAMES].corrwith(sub["label"]).abs().idxmax()
        r = float(sub[best].corr(sub["label"]))
        p = _fisher_z_pvalue(r, len(sub))
        print(f"  {label} (n={len(sub)}, P(label)={sub['label'].mean():.3f}): melhor='{best}' r={r:.4f} p={p:.5f}")

    print("\n" + "=" * 90)
    print("VEREDITO")
    print("=" * 90)
    auc = result.get("holdout_auc")
    acc = result.get("holdout_accuracy")
    baseline = result.get("holdout_baseline_accuracy")
    if auc is not None and acc is not None and baseline is not None and auc > 0.60 and acc > baseline:
        print("-> Candidato real: AUC > 0.60 e accuracy acima do baseline no holdout. Checar estabilidade temporal acima com cuidado antes de qualquer promocao.")
    else:
        print("-> Sem melhora convincente sobre o baseline. Detectar a TRANSICAO tambem nao resolveu — reforça que o teto esta no material bruto disponivel (preco+volume de um unico ativo), nao na formulacao do problema.")


if __name__ == "__main__":
    main()
