"""Tests whether feature ICs are real but regime-conditional, instead of
pooling every day together (which is what hid the signal in
scripts/cross_sectional_ic.py — see docs/data_phase_findings.md, "5 years,
IC flips sign between the 2022 bear market and the bull periods after").

Regime is computed once from NASDAQ (market-wide), not per-symbol — a
per-symbol regime would be circular with the cross-sectional features
being tested (same trap identified with the AUC=0.874 result in
scripts/regime_transition_experiment.py). Every symbol on a given date
gets the same regime label; this mirrors the RegimeFolio-style approach
suggested in the external review and the market-level regime already
computed in scripts/regime_timeline.py.

This is a diagnostic pass, not a promotion-readiness test: it answers
"does splitting by regime reveal something real?" using the full sample
per bucket. A regime bucket that shows a strong IC here would still need
the full walk-forward holdout + temporal-stability protocol (same as
every other experiment in this audit) before being trusted for anything
beyond "worth building the regime-conditional model."

Run: python -m scripts.regime_conditional_ic
     MARKET_HISTORY_PERIOD=5y python -m scripts.regime_conditional_ic
"""
from __future__ import annotations

import math
from statistics import NormalDist

import pandas as pd

from app.market_data import service as market_data_service
from scripts.compare_recommendations import DEFAULT_SYMBOLS, _load_prepared, _symbols
from scripts.cross_sectional_ic import MIN_SYMBOLS_PER_DAY, _build_panel, _daily_ic
from scripts.regime_transition_experiment import _regime_score

pd.set_option("display.width", 140)

BULL_THRESHOLD = 15.0
BEAR_THRESHOLD = -15.0
FEATURES_TO_TEST = ["annualized_volatility", "atr_pct", "rsi", "trend", "score"]


def _market_regime_by_date() -> pd.Series:
    """NASDAQ-100 futures regime_score, indexed by calendar date (one label
    per date, shared by every symbol that trades that day)."""
    from app.paper_simulator import MARKET_HISTORY_PERIOD

    nasdaq = market_data_service.get_bars("NQ=F", period=MARKET_HISTORY_PERIOD, interval="1d")
    if nasdaq.empty:
        nasdaq = market_data_service.get_bars("^NDX", period=MARKET_HISTORY_PERIOD, interval="1d")
    regime = _regime_score(nasdaq)
    score = regime["regime_score"].copy()
    score.index = pd.to_datetime(score.index)
    if score.index.tz is not None:
        score.index = score.index.tz_localize(None)
    score.index = score.index.normalize()
    return score[~score.index.duplicated(keep="last")]


def _label(score: float) -> str:
    if pd.isna(score):
        return "INDEFINIDO"
    if score >= BULL_THRESHOLD:
        return "BULL"
    if score <= BEAR_THRESHOLD:
        return "BEAR"
    return "NEUTRO"


def _fisher_z_pvalue(r: float, n: int) -> float | None:
    if n < 4 or abs(r) >= 1:
        return None
    z = math.atanh(r) * math.sqrt(n - 3)
    return 2 * (1 - NormalDist().cdf(abs(z)))


def _ic_summary(ic_series: pd.Series) -> dict:
    n = len(ic_series)
    if n == 0:
        return {"dias": 0, "IC_medio": None, "t_stat": None, "%dias_positivo": None}
    mean_ic = float(ic_series.mean())
    std_ic = float(ic_series.std())
    ir = mean_ic / std_ic if std_ic > 0 else None
    t_stat = ir * math.sqrt(n) if ir is not None else None
    return {
        "dias": n,
        "IC_medio": round(mean_ic, 4),
        "t_stat": round(t_stat, 2) if t_stat is not None else None,
        "%dias_positivo": round(float((ic_series > 0).mean()), 3),
    }


def main() -> None:
    symbols = _symbols() or DEFAULT_SYMBOLS
    prepared, benchmark, skipped = _load_prepared(symbols)
    if not prepared:
        raise SystemExit("Nenhum simbolo com historico suficiente.")

    panel = _build_panel(prepared, benchmark)
    market_regime = _market_regime_by_date()
    # panel["date"] comes from yfinance equity history (tz-aware, e.g. US/Eastern);
    # market_regime's index was explicitly stripped to tz-naive — normalize both to
    # the same (naive) representation before the lookup, or every date silently
    # fails to match and everything falls into "INDEFINIDO".
    naive_dates = panel["date"].dt.tz_localize(None) if panel["date"].dt.tz is not None else panel["date"]
    panel["regime"] = naive_dates.map(lambda d: _label(market_regime.get(d)))

    regime_counts = panel.drop_duplicates("date")["regime"].value_counts()
    print(f"Simbolos: {len(prepared)} | Amostras: {len(panel)}")
    print(f"Dias por regime (unicos, nao amostras): \n{regime_counts.to_string()}\n")

    for regime_label in ["BULL", "BEAR", "NEUTRO"]:
        sub = panel[panel["regime"] == regime_label]
        n_days = sub["date"].nunique()
        print("=" * 100)
        print(f"REGIME = {regime_label}  ({n_days} dias unicos, {len(sub)} amostras)")
        print("=" * 100)
        if n_days < 20:
            print("Poucos dias nesse regime — resultado pouco confiavel, so reportando por completude.\n")

        rows = []
        for feature in FEATURES_TO_TEST:
            ic_series = _daily_ic(sub, feature)
            summary = _ic_summary(ic_series)
            summary["feature"] = feature
            rows.append(summary)
        result_df = pd.DataFrame(rows).set_index("feature")
        if result_df["IC_medio"].notna().any():
            result_df = result_df.reindex(result_df["IC_medio"].abs().sort_values(ascending=False, na_position="last").index)
        print(result_df.to_string())
        print()

    print("=" * 100)
    print("LEITURA")
    print("=" * 100)
    print(
        "Compare o IC/t-stat do MESMO feature entre BULL e BEAR acima. Se o sinal so aparece\n"
        "(ou so e forte) num regime especifico, isso confirma a hipotese condicional-a-regime —\n"
        "proximo passo seria um modelo/filtro que so opera quando o regime bate, validado com\n"
        "walk-forward holdout dentro desse regime antes de qualquer promocao. Se o sinal continua\n"
        "fraco/instavel mesmo separado por regime, a hipotese condicional tambem nao se sustenta."
    )


if __name__ == "__main__":
    main()
