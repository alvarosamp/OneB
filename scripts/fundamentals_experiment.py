"""Tests whether fundamentals (a genuinely different data family from the
technical indicators exhausted in the prior experiments) carry cross-
sectional information about forward returns.

Point-in-time discipline: each price-date row is joined to the most recent
annual report whose FILING DATE (not period-end date) is <= that price
date. Using period-end date instead would leak ~1-2 months of look-ahead
per row (companies report weeks/months after their fiscal year closes) —
exactly the kind of mistake the EDA lesson on look-ahead bias warned about.
Rows before any report has been filed yet are dropped, not back-filled.

Candidate features (from FMP's free-tier annual key-metrics/income-
statement — see app/market_data/fmp_client.py):
  - earnings_yield       (cheapness — inverse P/E)
  - fcf_yield            (cheapness on cash generation)
  - roe                  (return on equity — quality)
  - roic                 (return on invested capital — quality)
  - net_debt_to_ebitda   (leverage — risk)
  - ev_to_ebitda         (valuation multiple)
  - net_margin           (profitability)
  - revenue_growth_yoy   (growth, computed from two consecutive filings)

Evaluated the same way the cross-sectional volatility signal was in
scripts/cross_sectional_ic.py: daily Spearman IC across the symbol
universe, THEN a temporal stability check (first half vs second half) —
the check that killed that earlier signal. A fundamentals signal that
doesn't survive that same check gets the same "don't promote" verdict.

Run: python -m scripts.fundamentals_experiment
"""
from __future__ import annotations

import math
from datetime import datetime
from statistics import NormalDist

import pandas as pd

from app import paper_simulator as sim
from app.market_data import fmp_client
from scripts.compare_recommendations import DEFAULT_SYMBOLS, _load_prepared, _symbols

pd.set_option("display.width", 140)

LABEL_HORIZON_DAYS = 5
MIN_SYMBOLS_PER_DAY = 10
FUNDAMENTAL_FEATURES = [
    "earnings_yield",
    "fcf_yield",
    "roe",
    "roic",
    "net_debt_to_ebitda",
    "ev_to_ebitda",
    "net_margin",
    "revenue_growth_yoy",
]


def _fetch_point_in_time_reports(symbol: str) -> list[dict]:
    """Merges key-metrics + income-statement on period-end date, keeps only
    filingDate + the candidate fundamental fields, sorted oldest-first.
    """
    key_metrics = {r["date"]: r for r in fmp_client.get_key_metrics(symbol)}
    income = fmp_client.get_income_statement(symbol)

    reports = []
    for row in income:
        period_end = row.get("date")
        km = key_metrics.get(period_end)
        if km is None or not row.get("filingDate"):
            continue
        revenue = row.get("revenue")
        net_income = row.get("netIncome")
        reports.append(
            {
                "filing_date": row["filingDate"],
                "period_end": period_end,
                "revenue": revenue,
                "earnings_yield": km.get("earningsYield"),
                "fcf_yield": km.get("freeCashFlowYield"),
                "roe": km.get("returnOnEquity"),
                "roic": km.get("returnOnInvestedCapital"),
                "net_debt_to_ebitda": km.get("netDebtToEBITDA"),
                "ev_to_ebitda": km.get("evToEBITDA"),
                "net_margin": (net_income / revenue) if revenue else None,
            }
        )
    reports.sort(key=lambda r: r["period_end"])
    # revenue growth needs the PRIOR report, computed here so it's already
    # attached to the report where it becomes knowable (same filing_date)
    for i in range(1, len(reports)):
        prev_rev, cur_rev = reports[i - 1]["revenue"], reports[i]["revenue"]
        reports[i]["revenue_growth_yoy"] = ((cur_rev / prev_rev) - 1) * 100 if prev_rev else None
    if reports:
        reports[0]["revenue_growth_yoy"] = None
    return reports


def _latest_report_as_of(reports: list[dict], price_date: pd.Timestamp) -> dict | None:
    price_date_naive = price_date.tz_localize(None) if price_date.tzinfo else price_date
    applicable = [r for r in reports if datetime.fromisoformat(r["filing_date"]) <= price_date_naive]
    return applicable[-1] if applicable else None


def _build_dataset(prepared: dict, benchmark: dict | None, reports_by_symbol: dict) -> pd.DataFrame:
    rows = []
    for symbol, data in prepared.items():
        history = data["history"]
        reports = reports_by_symbol.get(symbol, [])
        limit = len(history) - LABEL_HORIZON_DAYS
        for i in range(0, limit):
            features = sim.feature_vector(data, i, benchmark)
            if features is None:
                continue
            report = _latest_report_as_of(reports, history.index[i])
            if report is None:
                continue
            fundamentals = {name: report.get(name) for name in FUNDAMENTAL_FEATURES}
            if any(v is None for v in fundamentals.values()):
                continue

            price = float(history["close"].iloc[i])
            fwd_return = (float(history["close"].iloc[i + LABEL_HORIZON_DAYS]) / price - 1) * 100
            # date, not row_index — see scripts/research_folds.py docstring
            row = {"symbol": symbol, "date": history.index[i].normalize(), "fwd_return_5d": fwd_return}
            row.update(dict(zip(sim.FEATURE_NAMES, features)))
            row.update(fundamentals)
            rows.append(row)
    return pd.DataFrame(rows)


def _daily_ic(panel: pd.DataFrame, feature: str) -> pd.Series:
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
    if n == 0:
        return {"dias_avaliados": 0, "IC_medio": None, "IC_IR": None, "t_stat": None, "%dias_positivo": None}
    mean_ic = float(ic_series.mean())
    std_ic = float(ic_series.std())
    ir = mean_ic / std_ic if std_ic > 0 else None
    t_stat = ir * math.sqrt(n) if ir is not None else None
    return {
        "dias_avaliados": n,
        "IC_medio": round(mean_ic, 4),
        "IC_IR": round(ir, 4) if ir is not None else None,
        "t_stat": round(t_stat, 2) if t_stat is not None else None,
        "%dias_positivo": round(float((ic_series > 0).mean()), 3),
    }


def main() -> None:
    symbols = _symbols() or DEFAULT_SYMBOLS
    prepared, benchmark, skipped = _load_prepared(symbols)
    if not prepared:
        raise SystemExit("Nenhum simbolo com historico suficiente.")

    print(f"Buscando fundamentals (FMP, annual, point-in-time) para {len(prepared)} simbolos...")
    reports_by_symbol = {}
    coverage_rows = []
    for symbol in prepared:
        reports = _fetch_point_in_time_reports(symbol)
        reports_by_symbol[symbol] = reports
        coverage_rows.append({"symbol": symbol, "reports_validos": len(reports)})
    coverage_df = pd.DataFrame(coverage_rows)
    no_data = coverage_df[coverage_df["reports_validos"] == 0]["symbol"].tolist()
    if no_data:
        print(f"ATENCAO — sem fundamentals utilizaveis: {no_data}")

    panel = _build_dataset(prepared, benchmark, reports_by_symbol)
    if panel.empty:
        raise SystemExit("Nenhuma linha com fundamentals point-in-time valida — abortando.")

    symbols_per_day = panel.groupby("date").size()
    print(f"\nAmostras com fundamentals validos: {len(panel)} | simbolos cobertos: {panel['symbol'].nunique()}")
    print(f"Simbolos por dia: min={symbols_per_day.min()} mediana={int(symbols_per_day.median())}\n")

    print("=" * 100)
    print("INFORMATION COEFFICIENT — fundamentals vs retorno futuro de 5d, cross-sectional")
    print("Mesmo benchmark academico da vez anterior: 0.01-0.05 fraco | 0.05-0.10 solido | 0.10+ excepcional")
    print("=" * 100)
    results = []
    for feature in FUNDAMENTAL_FEATURES:
        summary = _ic_summary(_daily_ic(panel, feature))
        summary["feature"] = feature
        results.append(summary)
    results_df = pd.DataFrame(results).set_index("feature")
    results_df = results_df.reindex(results_df["IC_medio"].abs().sort_values(ascending=False).index)
    print(results_df.to_string())

    print("\n" + "=" * 100)
    print("ESTABILIDADE TEMPORAL da melhor feature (primeira vs segunda metade)")
    print("=" * 100)
    best_feature = results_df.index[0]
    days = sorted(panel["date"].unique())
    midpoint = days[len(days) // 2]
    for label, sub in [("Primeira metade", panel[panel["date"] < midpoint]), ("Segunda metade", panel[panel["date"] >= midpoint])]:
        summary = _ic_summary(_daily_ic(sub, best_feature))
        print(f"  {label}: {summary}")

    print("\n" + "=" * 100)
    print("VEREDITO")
    print("=" * 100)
    best_ic = results_df.iloc[0]["IC_medio"]
    best_t = results_df.iloc[0]["t_stat"]
    if best_ic is not None and abs(best_ic) >= 0.05 and best_t is not None and abs(best_t) >= 2:
        print(
            f"-> '{best_feature}' mostra IC na faixa solida (>=0.05) com significancia estatistica. "
            "Verificar a estabilidade temporal acima antes de qualquer promocao — mesmo protocolo "
            "que derrubou o sinal de volatilidade cross-sectional anteriormente."
        )
    elif best_ic is not None and abs(best_ic) >= 0.01:
        print(
            f"-> '{best_feature}' mostra sinal fraco (IC={best_ic}). Mesma leitura da vez anterior: nao "
            "sustenta uma estrategia sozinho, mas é evidencia real, nao ruido — candidato a compor um "
            "score multi-fator junto com o que sobreviver da parte tecnica."
        )
    else:
        print(
            "-> Nenhum fundamento testado mostra sinal acima do ruido nesse universo/janela. Combinado "
            "com o resultado da parte tecnica, isso sugere que ou o horizonte de 5 dias é curto demais "
            "para fundamentals (que tipicamente atuam em horizontes de meses, não dias) ou o universo de "
            "48 mega-caps/blue-chips é eficiente demais para esse tipo de fator também."
        )


if __name__ == "__main__":
    main()
