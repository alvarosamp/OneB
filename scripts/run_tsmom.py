"""Executa o teste pré-registrado tsmom_v1 (tendência de 1, 3 e 12 meses).

    python scripts/run_tsmom.py

Lê os candles diários de D:/OneB/market-data/dukascopy-daily, aplica as regras
congeladas no LOCK e grava o relatório em D:/OneB/research/tsmom_v1/.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import trend  # noqa: E402
from app.research_paths import RESEARCH_ROOT  # noqa: E402
from app.setups import load_preregistered  # noqa: E402

OUT = RESEARCH_ROOT / "tsmom_v1"


def _window(series: pd.Series, period: dict) -> pd.Series:
    lo, hi = pd.Period(period["from_inclusive"], "M"), pd.Period(period["to_exclusive"], "M")
    return series[(series.index >= lo) & (series.index < hi)]


def main() -> None:
    spec, spec_sha = load_preregistered("tsmom_v1")
    manifest = json.loads((trend.DAILY_DIR.parent / "manifest.json").read_text(encoding="utf-8"))
    classes = {i: group for group in ("equity_index", "commodity", "fx") for i in spec["universe"][group]}
    frames, excluded = {}, {}
    for instrument in classes:
        info = manifest.get(instrument)
        if info is None:
            excluded[instrument] = "sem dados baixados"
        elif "failed" in info:
            excluded[instrument] = f"falha de dados na fonte: {info['failed']}"
        elif info["max_gap_weekdays"] > 5 or (info["min_full_year_rows"] is not None and info["min_full_year_rows"] < 200):
            excluded[instrument] = f"buraco de {info['max_gap_weekdays']} dias úteis ou ano com {info['min_full_year_rows']} pregões"
        else:
            frames[instrument] = trend.load_daily(instrument)
    params = trend.TrendParams()
    period, recent = spec["evaluation"]["period"], spec["evaluation"]["recent_window"]

    combined, table = trend.portfolio_monthly(frames, params)
    combined = _window(combined, period)
    long_only, _ = trend.portfolio_monthly(frames, params, long_only=True)
    long_only = _window(long_only, period)
    primary = trend.summary(combined)
    recent_series = _window(combined, recent)
    decision = trend.verdict(tuple(primary["ci95"]), float(recent_series.mean()) if len(recent_series) else None)

    horizons = {}
    for L in params.lookbacks:
        series, _ = trend.portfolio_monthly(frames, params, lookbacks=(L,))
        v = _window(series, period).dropna().to_numpy()
        lo, hi = trend.ci(v, alpha=0.05 / len(params.lookbacks))
        horizons[trend.HORIZON_LABEL[L]] = {**trend.summary(pd.Series(v)), "ci_bonferroni": [round(lo, 5), round(hi, 5)]}

    table = table[(table.index >= pd.Period(period["from_inclusive"], "M")) & (table.index < pd.Period(period["to_exclusive"], "M"))]
    by_class = {g: trend.summary(table[[c for c in table.columns if classes[c] == g]].mean(axis=1, skipna=True))
                for g in ("equity_index", "commodity", "fx")}
    by_year = {str(y): round(float(((1 + combined[combined.index.year == y]).prod()) - 1), 4) for y in sorted(set(combined.index.year))}
    by_instrument = {c: {"class": classes[c], "months": int(table[c].notna().sum()),
                         "mean_monthly": round(float(table[c].mean()), 5)} for c in table.columns}

    beyond = trend.alpha_vs(combined, long_only)
    beyond["badge"] = beyond["alpha_ci95"][0] > 0
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "test": spec["test"], "spec_sha256": spec_sha,
        "universe_used": sorted(frames), "excluded": excluded,
        "primary_combined": primary, "recent_window": trend.summary(recent_series), "verdict": decision,
        "horizons": horizons, "long_only_baseline": trend.summary(long_only), "beyond_long_only": beyond,
        "by_class": by_class, "by_year": by_year, "by_instrument": by_instrument,
        "big_moves": {i: manifest[i]["big_moves"] for i in frames if manifest[i]["big_moves"]},
        "notes": spec["costs"]["note"],
        "monthly_combined": {str(k): round(float(v), 6) for k, v in combined.items()},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"tsmom_v1_{datetime.now(timezone.utc):%Y%m%d}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    # Resumo pequeno e versionado para o app (produção não tem o HD externo).
    summary_path = ROOT / "app" / "research_results" / "tsmom_v1.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    keep = ("generated_at", "test", "spec_sha256", "universe_used", "excluded", "primary_combined", "recent_window", "verdict",
            "horizons", "long_only_baseline", "beyond_long_only", "by_class", "by_year", "by_instrument", "notes")
    summary_path.write_text(json.dumps({k: report[k] for k in keep}, ensure_ascii=False, indent=2), encoding="utf-8")
    brief = {k: report[k] for k in ("universe_used", "excluded", "primary_combined", "recent_window", "verdict", "horizons",
                                     "long_only_baseline", "beyond_long_only", "by_class", "by_year")}
    print(json.dumps(brief, ensure_ascii=False, indent=1))
    print(f"\nRelatório: {path}")


if __name__ == "__main__":
    main()
