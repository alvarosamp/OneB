"""Scans label horizons/thresholds to see if the poor holdout result from
scripts/train_probability_model.py is a label problem (fixable) or a
features problem (needs new features, not just a new label).

For each (horizon_days, threshold_pct) combination, builds forward_return
labels the same way scripts/train_probability_model.py does and reports:
  - class balance / baseline accuracy
  - correlation of each existing feature with that label

Read-only / no side effects — doesn't touch the saved model. Run
scripts/train_probability_model.py separately once a promising
configuration is found.
"""
from __future__ import annotations

import pandas as pd

from app import paper_simulator as sim
from scripts.compare_recommendations import DEFAULT_SYMBOLS, _load_prepared, _symbols

HORIZONS_DAYS = [1, 3, 5, 10, 20]
THRESHOLDS_PCT = [0.0, 0.5, 1.0]


def _build_dataset_multi_horizon(prepared: dict, benchmark: dict | None, max_horizon: int) -> pd.DataFrame:
    rows = []
    for symbol, data in prepared.items():
        history = data["history"]
        limit = len(history) - max_horizon
        for i in range(0, limit):
            features = sim.feature_vector(data, i, benchmark)
            if features is None:
                continue
            price = float(history["close"].iloc[i])
            row = {"symbol": symbol}
            for name, value in zip(sim.FEATURE_NAMES, features):
                row[name] = value
            for h in HORIZONS_DAYS:
                future_price = float(history["close"].iloc[i + h])
                row[f"fwd_return_{h}d"] = (future_price / price - 1) * 100
            rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    symbols = _symbols() or DEFAULT_SYMBOLS
    prepared, benchmark, skipped = _load_prepared(symbols)
    if not prepared:
        raise SystemExit("Nenhum simbolo com historico suficiente.")

    df = _build_dataset_multi_horizon(prepared, benchmark, max(HORIZONS_DAYS))
    print(f"Amostras: {len(df)} | simbolos: {len(prepared)} | descartados: {skipped}\n")

    feature_cols = sim.FEATURE_NAMES
    summary_rows = []
    for h in HORIZONS_DAYS:
        fwd_col = f"fwd_return_{h}d"
        for threshold in THRESHOLDS_PCT:
            label = (df[fwd_col] > threshold).astype(int)
            positive_rate = label.mean()
            baseline = max(positive_rate, 1 - positive_rate)
            corr = df[feature_cols].corrwith(label)
            best_feature = corr.abs().idxmax()
            summary_rows.append(
                {
                    "horizon_dias": h,
                    "threshold_pct": threshold,
                    "positive_rate": round(float(positive_rate), 4),
                    "baseline_accuracy": round(float(baseline), 4),
                    "melhor_feature": best_feature,
                    "melhor_|corr|": round(float(corr.abs().max()), 4),
                    "media_|corr|_todas_features": round(float(corr.abs().mean()), 4),
                }
            )

    summary = pd.DataFrame(summary_rows).sort_values("melhor_|corr|", ascending=False)
    pd.set_option("display.width", 140)
    print(summary.to_string(index=False))

    print(
        "\nLeitura: 'melhor_|corr|' é a correlação linear mais forte entre QUALQUER feature atual e esse\n"
        "label. Valores ainda baixos (<0.10) em TODAS as combinações confirmam que o problema não é o\n"
        "horizonte do label — é que as 11 features atuais carregam pouca informação preditiva, ponto."
    )


if __name__ == "__main__":
    main()
