"""EDA / data-quality audit for the Signal Quality AI dataset and the
macro/cross-asset instruments the regime engine depends on.

Deliberately reuses the *exact* pipeline that already builds the training
set (app.paper_simulator + scripts/train_probability_model.py) instead of
recomputing features a different way — an EDA that inspects different code
than what trains the model would answer the wrong question.

Usage:
    python -m scripts.eda_report
    PAPER_SIM_SYMBOLS=AAPL,MSFT python -m scripts.eda_report   # subset
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from app import paper_simulator as sim
from app.market_data import macro_data
from scripts.compare_recommendations import DEFAULT_SYMBOLS, _load_prepared, _symbols

pd.set_option("display.width", 120)


def _print_header(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


# ---------------------------------------------------------------------------
# 1. Cobertura de histórico por símbolo (gaps, tamanho, período)
# ---------------------------------------------------------------------------
def audit_history_coverage(prepared: dict, skipped: list[str]) -> None:
    _print_header("1. COBERTURA DE HISTORICO (OHLCV diario, yfinance)")
    if skipped:
        print(f"Descartados por historico insuficiente (<120 candles): {skipped}")

    rows = []
    for symbol, data in prepared.items():
        history = data["history"]
        idx = history.index
        gaps = idx.to_series().diff().dt.days.dropna()
        # Dias uteis esperam ~1-3 dias entre candles diarios (fins de semana/feriados);
        # qualquer coisa acima de 5 é um buraco real no feed.
        max_gap = int(gaps.max()) if not gaps.empty else 0
        big_gaps = int((gaps > 5).sum())
        rows.append(
            {
                "symbol": symbol,
                "candles": len(history),
                "inicio": idx.min().date(),
                "fim": idx.max().date(),
                "maior_gap_dias": max_gap,
                "gaps_suspeitos(>5d)": big_gaps,
            }
        )
    df = pd.DataFrame(rows).sort_values("gaps_suspeitos(>5d)", ascending=False)
    print(df.to_string(index=False))


# ---------------------------------------------------------------------------
# 2. Dataset de features/labels (o que o probability_model realmente treina)
# ---------------------------------------------------------------------------
def _build_full_dataset(prepared: dict, benchmark: dict | None) -> pd.DataFrame:
    """Same feature_vector + label rule as scripts/train_probability_model.py,
    but over the FULL available range (no walk-forward split) — this is an
    audit of the raw material, not a training run.
    """
    rows = []
    for symbol, data in prepared.items():
        history = data["history"]
        limit = len(history) - 5  # precisa de 5 candles futuros pro forward_return
        for i in range(0, limit):
            features = sim.feature_vector(data, i, benchmark)
            if features is None:
                continue
            price = float(history["close"].iloc[i])
            forward_return = (float(history["close"].iloc[i + 5]) / price - 1) * 100
            label = 1 if forward_return > 0.5 else 0
            rows.append([symbol, history.index[i]] + features + [forward_return, label])

    columns = ["symbol", "date"] + sim.FEATURE_NAMES + ["forward_return_5d_pct", "label"]
    return pd.DataFrame(rows, columns=columns)


def audit_dataset(df: pd.DataFrame) -> None:
    _print_header("2. DATASET DE TREINO (Signal Quality AI) — visao geral")
    print(f"Total de amostras utilizaveis: {len(df)}")
    print(f"Amostras por simbolo:\n{df.groupby('symbol').size().sort_values(ascending=False).to_string()}")

    _print_header("2a. Balanceamento de classes")
    positive_rate = df["label"].mean()
    baseline_accuracy = max(positive_rate, 1 - positive_rate)
    print(f"P(retorno 5d > 0.5%) = {positive_rate:.4f}")
    print(f"Baseline accuracy (sempre prever a classe majoritaria) = {baseline_accuracy:.4f}")
    print("Qualquer modelo reportando accuracy PROXIMA ou ABAIXO desse baseline nao tem sinal real.")

    _print_header("2b. Estatisticas por feature (NaN, distribuicao)")
    feature_cols = sim.FEATURE_NAMES
    stats = df[feature_cols].describe().T
    stats["nan_count"] = df[feature_cols].isna().sum()
    stats["nan_pct"] = (stats["nan_count"] / len(df) * 100).round(2)
    print(stats.to_string())
    high_nan = stats[stats["nan_pct"] > 5]
    if not high_nan.empty:
        print(f"\nATENCAO — features com >5% de NaN (warm-up period ou dado faltante):\n{high_nan.index.tolist()}")

    _print_header("2c. Correlacao de cada feature com o label (poder preditivo bruto)")
    corr_with_label = df[feature_cols + ["label"]].corr(numeric_only=True)["label"].drop("label").sort_values(
        key=abs, ascending=False
    )
    print(corr_with_label.to_string())
    print(
        "\nCorrelacao linear e um proxy grosseiro (o modelo real e logistico, nao linear puro), "
        "mas uma feature com correlacao ~0 com o label e candidata a ser removida ou repensada."
    )

    _print_header("2d. Correlacao entre features (redundancia)")
    feat_corr = df[feature_cols].corr(numeric_only=True)
    redundant = []
    for i, a in enumerate(feature_cols):
        for b in feature_cols[i + 1 :]:
            c = feat_corr.loc[a, b]
            if abs(c) >= 0.85:
                redundant.append((a, b, round(float(c), 3)))
    if redundant:
        print("Pares de features com |correlacao| >= 0.85 (candidatas a redundantes):")
        for a, b, c in redundant:
            print(f"  {a} <-> {b}: {c}")
    else:
        print("Nenhum par de features com correlacao >= 0.85 — sem redundancia obvia.")

    _print_header("2e. Look-ahead sanity check")
    print(
        "Cada linha usa feature calculada no candle i (so passado ate i) e label calculado a partir\n"
        "do close em i+5 (futuro). Nenhuma feature deveria depender de i+1..i+5 — isso ja e garantido\n"
        "pelo app.paper_simulator.feature_vector (fonte unica usada tanto aqui quanto no treino real),\n"
        "entao nao ha checagem adicional a fazer aqui alem de confirmar que essa e a MESMA funcao."
    )


# ---------------------------------------------------------------------------
# 3. Cobertura dos instrumentos macro (FRED + yfinance)
# ---------------------------------------------------------------------------
def audit_macro_coverage() -> None:
    _print_header("3. COBERTURA DOS INSTRUMENTOS MACRO (regime engine)")
    rows = []
    for key, (source, symbol, name) in macro_data.MACRO_INSTRUMENTS.items():
        history = macro_data.get_macro_history(key, period="6mo", interval="1d")
        if history.empty:
            rows.append({"key": key, "fonte": source, "symbol": symbol, "candles": 0, "status": "SEM DADOS"})
            continue
        close = history["close"].dropna()
        rows.append(
            {
                "key": key,
                "fonte": source,
                "symbol": symbol,
                "candles": len(close),
                "inicio": close.index.min().date(),
                "fim": close.index.max().date(),
                "status": "OK" if len(close) > 30 else "POUCO HISTORICO",
            }
        )
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    missing = df[df["status"] != "OK"]
    if not missing.empty:
        print(
            f"\nATENCAO — instrumentos sem dado utilizavel: {missing['key'].tolist()}. "
            "Se for um instrumento 'fred', confirme FRED_API_KEY no .env."
        )


def main() -> None:
    symbols = _symbols() or DEFAULT_SYMBOLS
    print(f"Simbolos analisados: {symbols}")
    prepared, benchmark, skipped = _load_prepared(symbols)
    if not prepared:
        raise SystemExit("Nenhum simbolo com historico suficiente — nada a auditar.")

    audit_history_coverage(prepared, skipped)
    df = _build_full_dataset(prepared, benchmark)
    audit_dataset(df)
    audit_macro_coverage()

    _print_header("RESUMO")
    print(
        json.dumps(
            {
                "simbolos_ok": len(prepared),
                "simbolos_descartados": skipped,
                "amostras_dataset": len(df),
                "positive_rate": round(float(df["label"].mean()), 4),
                "baseline_accuracy": round(float(max(df["label"].mean(), 1 - df["label"].mean())), 4),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
