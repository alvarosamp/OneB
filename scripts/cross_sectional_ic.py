"""Cross-sectional Information Coefficient (IC) analysis — the evaluation
framework actually used in the quant literature and industry, as opposed to
the per-stock absolute-return classification used so far in
scripts/train_probability_model.py.

Why this is a different (and more standard) question:

  scripts/train_probability_model.py asks, per stock in isolation:
      "will THIS stock's return in 5 days exceed +0.5%?"
  That mixes time-series variation (the whole market went up that week)
  with cross-sectional variation (this stock did better than its peers)
  into one label — and pools all symbols/dates together for one global
  accuracy number.

  The asset-pricing ML literature (Gu, Kelly & Xiu 2020, "Empirical Asset
  Pricing via Machine Learning", and the cross-sectional factor literature
  before it) instead asks, per DAY, across the universe of stocks:
      "does this signal rank stocks in the order they actually performed,
       relative to each other, that day?"
  That's the Information Coefficient: the (Spearman) rank correlation
  between a signal and forward return, computed separately per day and
  averaged over time. Published single factors typically show IC in the
  0.02-0.07 range; 0.05-0.10 is already considered a solid, tradeable
  signal by working quant funds — nothing like the >0.3 correlation a
  pooled classification accuracy number implicitly demands to "look good".
  Sources checked during this session: Gu/Kelly/Xiu (2020, RFS), the IC
  benchmark ranges summarized in general quant-finance references
  (Pomegra IC wiki, "Exploring Classic Quantitative Strategies" arXiv
  2202.11309).

This script computes daily cross-sectional IC for every one of the 11
production features (app.paper_simulator.FEATURE_NAMES) against 5-day
forward return, using the SAME symbols/history as everything else in this
audit so results are directly comparable.

Run: python -m scripts.cross_sectional_ic
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from app import paper_simulator as sim
from scripts.compare_recommendations import DEFAULT_SYMBOLS, _load_prepared, _symbols

pd.set_option("display.width", 140)

LABEL_HORIZON_DAYS = 5
MIN_SYMBOLS_PER_DAY = 10  # abaixo disso, o IC do dia é ruído demais pra contar


def _build_panel(prepared: dict, benchmark: dict | None) -> pd.DataFrame:
    rows = []
    for symbol, data in prepared.items():
        history = data["history"]
        limit = len(history) - LABEL_HORIZON_DAYS
        for i in range(0, limit):
            features = sim.feature_vector(data, i, benchmark)
            if features is None:
                continue
            price = float(history["close"].iloc[i])
            fwd_return = (float(history["close"].iloc[i + LABEL_HORIZON_DAYS]) / price - 1) * 100
            # "date" (the calendar day), not row_index, is what makes rows from
            # different symbols comparable — row_index only lined up with the same
            # calendar date by coincidence while every symbol had identical-length
            # histories (see scripts/research_folds.py docstring for why that
            # stops being safe once history windows/IPO dates diverge).
            row = {"symbol": symbol, "date": history.index[i].normalize(), "fwd_return_5d": fwd_return}
            row.update(dict(zip(sim.FEATURE_NAMES, features)))
            rows.append(row)
    return pd.DataFrame(rows)


def _daily_ic(panel: pd.DataFrame, feature: str) -> pd.Series:
    """Spearman rank correlation between `feature` and forward return,
    computed separately for each calendar date, across symbols.
    """
    ics = {}
    for the_date, group in panel.groupby("date"):
        if len(group) < MIN_SYMBOLS_PER_DAY:
            continue
        ic = group[feature].corr(group["fwd_return_5d"], method="spearman")
        if pd.notna(ic):
            ics[the_date] = ic
    return pd.Series(ics)


def _ic_summary(ic_series: pd.Series) -> dict:
    n = len(ic_series)
    mean_ic = float(ic_series.mean())
    std_ic = float(ic_series.std())
    ir = mean_ic / std_ic if std_ic > 0 else None
    t_stat = ir * math.sqrt(n) if ir is not None else None
    pct_positive = float((ic_series > 0).mean())
    return {
        "dias_avaliados": n,
        "IC_medio": round(mean_ic, 4),
        "IC_std": round(std_ic, 4),
        "IC_IR": round(ir, 4) if ir is not None else None,
        "t_stat": round(t_stat, 2) if t_stat is not None else None,
        "%dias_positivo": round(pct_positive, 3),
    }


def _classify(mean_ic: float) -> str:
    a = abs(mean_ic)
    if a >= 0.10:
        return "EXCEPCIONAL (raro — checar overfitting antes de confiar)"
    if a >= 0.05:
        return "SOLIDO (faixa em que fundos quant reais operam)"
    if a >= 0.01:
        return "FRACO mas potencialmente aproveitavel"
    return "SEM SINAL (dentro do ruido)"


def main() -> None:
    symbols = _symbols() or DEFAULT_SYMBOLS
    prepared, benchmark, skipped = _load_prepared(symbols)
    if not prepared:
        raise SystemExit("Nenhum simbolo com historico suficiente.")

    panel = _build_panel(prepared, benchmark)
    symbols_per_day = panel.groupby("date").size()
    print(f"Simbolos: {len(prepared)} | Amostras: {len(panel)}")
    print(
        f"Simbolos disponiveis por dia: min={symbols_per_day.min()} "
        f"mediana={int(symbols_per_day.median())} max={symbols_per_day.max()}\n"
    )

    print("=" * 100)
    print(f"INFORMATION COEFFICIENT diario — feature vs retorno futuro de {LABEL_HORIZON_DAYS}d, cross-sectional")
    print("Benchmark academico/industria: IC 0.01-0.05 fraco-aproveitavel | 0.05-0.10 solido | 0.10+ excepcional")
    print("=" * 100)

    results = []
    for feature in sim.FEATURE_NAMES:
        ic_series = _daily_ic(panel, feature)
        if ic_series.empty:
            continue
        summary = _ic_summary(ic_series)
        summary["feature"] = feature
        summary["classificacao"] = _classify(summary["IC_medio"])
        results.append(summary)

    results_df = pd.DataFrame(results).set_index("feature")
    results_df = results_df.reindex(results_df["IC_medio"].abs().sort_values(ascending=False).index)
    print(results_df.to_string())

    best = results_df.iloc[0]
    print("\n" + "=" * 100)
    print("LEITURA")
    print("=" * 100)
    print(
        f"Melhor feature (cross-sectional): '{best.name}' — IC medio={best['IC_medio']}, "
        f"IR={best['IC_IR']}, t-stat={best['t_stat']}, positivo em {best['%dias_positivo']*100:.1f}% dos dias.\n"
    )
    if abs(best["IC_medio"]) >= 0.05:
        print(
            "-> Ao contrario da avaliacao por accuracy/AUC absoluta feita antes, aqui SIM aparece sinal na\n"
            "faixa considerada solida pela industria. Isso sugere que o problema não era falta de\n"
            "informação nas features — era o FORMATO da pergunta (label absoluto pooled) escondendo um\n"
            "sinal que só aparece quando comparamos as ações ENTRE SI no mesmo dia. Vale reformular o\n"
            "probability_model para prever RANKING cross-sectional em vez de limiar absoluto de retorno."
        )
    elif abs(best["IC_medio"]) >= 0.01:
        print(
            "-> Sinal fraco mas não nulo, na faixa 'aproveitavel' da literatura. Sozinho não sustenta uma\n"
            "estrategia, mas é evidência de que a formulação cross-sectional capta mais informação que a\n"
            "formulação absoluta usada até agora — vale compor várias features fracas (como um fundo quant\n"
            "faria) em vez de descartar a abordagem inteira."
        )
    else:
        print(
            "-> Mesmo na formulação cross-sectional (o padrão da literatura), nenhuma feature isolada\n"
            "mostra IC acima do ruído. Isso é evidência mais forte de que o teto está genuinamente nas\n"
            "features/dado disponível, não apenas no formato da pergunta."
        )


if __name__ == "__main__":
    main()
