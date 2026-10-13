"""Sensibilidade do tsmom_v1: os 6 excluídos substituídos por séries diárias gratuitas do Yahoo.

    python scripts/run_tsmom_sensitivity.py

NÃO substitui o resultado primário (pré-registrado, dados Dukascopy). Mesma regra, mesmos
parâmetros, mesmo período; só o universo é completado com outra fonte. A Dukascopy bloqueou
o acesso do nosso IP ao feed em 09-10/10/2026, então os excluídos não puderam ser refeitos lá.

Ressalvas de fonte:
- Índices (^AXJO, ^HSI, ^STOXX50E) são o índice à vista, como os CFDs: sem problema de rolagem.
- Brent, gás e cobre (BZ=F, NG=F, HG=F) são futuros contínuos SEM ajuste de rolagem: o salto
  na troca de contrato entra como retorno falso. Por isso há duas variantes (+3 índices; +6).
- Sem bid/ask no Yahoo: o spread é a mediana relativa da mesma classe nos CFDs da Dukascopy.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import trend  # noqa: E402
from app.research_paths import RESEARCH_ROOT  # noqa: E402
from app.setups import load_preregistered  # noqa: E402
from run_tsmom import _window  # noqa: E402

CACHE = Path(r"D:\OneB\market-data\yahoo-daily")
SUBSTITUTES = {
    "ausidxaud": ("^AXJO", "equity_index"), "hkgidxhkd": ("^HSI", "equity_index"), "eusidxeur": ("^STOXX50E", "equity_index"),
    "brentcmdusd": ("BZ=F", "commodity"), "gascmdusd": ("NG=F", "commodity"), "coppercmdusd": ("HG=F", "commodity"),
}


def yahoo_close(ticker: str) -> pd.Series:
    path = CACHE / f"{ticker.replace('^', '_').replace('=', '_')}.csv"
    if not path.exists():
        import yfinance as yf
        data = yf.download(ticker, start="2010-01-01", end="2026-09-30", auto_adjust=False, progress=False)
        if data.empty:
            raise RuntimeError(f"Yahoo sem dados para {ticker}")
        close = data["Close"].squeeze().dropna()
        CACHE.mkdir(parents=True, exist_ok=True)
        close.rename("close").to_csv(path, index_label="date")
    frame = pd.read_csv(path, parse_dates=["date"], index_col="date")
    close = frame["close"].astype(float)
    close.index = pd.DatetimeIndex(close.index).tz_localize(None).normalize()
    return close[close > 0]


def run(frames: dict, classes: dict, period: dict, recent: dict) -> dict:
    params = trend.TrendParams()
    combined, table = trend.portfolio_monthly(frames, params)
    combined = _window(combined, period)
    long_only = _window(trend.portfolio_monthly(frames, params, long_only=True)[0], period)
    table = table[(table.index >= pd.Period(period["from_inclusive"], "M")) & (table.index < pd.Period(period["to_exclusive"], "M"))]
    recent_series = _window(combined, recent)
    out = {
        "universe": sorted(frames), "combined": trend.summary(combined), "recent_window": trend.summary(recent_series),
        "long_only": trend.summary(long_only), "beyond_long_only": trend.alpha_vs(combined, long_only),
        "by_class": {g: trend.summary(table[[c for c in table.columns if classes[c] == g]].mean(axis=1, skipna=True))
                     for g in ("equity_index", "commodity", "fx")},
        "by_instrument": {c: round(float(table[c].mean()), 5) for c in table.columns if c in SUBSTITUTES},
    }
    out["verdict"] = trend.verdict(tuple(out["combined"]["ci95"]), float(recent_series.mean()) if len(recent_series) else None)
    return out


def main() -> None:
    spec, spec_sha = load_preregistered("tsmom_v1")
    primary = json.loads((ROOT / "app" / "research_results" / "tsmom_v1.json").read_text(encoding="utf-8"))
    classes = {i: g for g in ("equity_index", "commodity", "fx") for i in spec["universe"][g]}
    base = {i: trend.load_daily(i) for i in primary["universe_used"]}
    rel_spread = {g: float(pd.concat([(f["spread"] / f["close"]) for i, f in base.items() if classes[i] == g]).median())
                  for g in ("equity_index", "commodity")}
    subs = {}
    for inst, (ticker, group) in SUBSTITUTES.items():
        close = yahoo_close(ticker)
        subs[inst] = pd.DataFrame({"close": close, "spread": close * rel_spread[group]})
        print(f"{inst:13s} <- {ticker:10s} {close.index.min().date()}..{close.index.max().date()} {len(close)} pregões", flush=True)
    period, recent = spec["evaluation"]["period"], spec["evaluation"]["recent_window"]
    indices = [i for i, (_, g) in SUBSTITUTES.items() if g == "equity_index"]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "test": "tsmom_v1_sensitivity", "spec_sha256": spec_sha,
        "status": "DESCRIPTIVE_ONLY: não substitui o resultado primário pré-registrado",
        "substitutes": {k: v[0] for k, v in SUBSTITUTES.items()}, "assumed_relative_spread": rel_spread,
        "primary_for_reference": {"combined": primary["primary_combined"], "verdict": primary["verdict"]},
        "plus_3_indices": run({**base, **{i: subs[i] for i in indices}}, classes, period, recent),
        "plus_all_6": run({**base, **subs}, classes, period, recent),
        "caveats": __doc__.split("Ressalvas de fonte:")[1].strip(),
    }
    out = RESEARCH_ROOT / "tsmom_v1"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"tsmom_v1_sensitivity_{datetime.now(timezone.utc):%Y%m%d}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "app" / "research_results" / "tsmom_v1_sensitivity.json").write_text(
        json.dumps({k: v for k, v in report.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
    for name in ("plus_3_indices", "plus_all_6"):
        r = report[name]
        print(name, json.dumps({k: r[k] for k in ("combined", "recent_window", "verdict", "by_class", "by_instrument")},
                               ensure_ascii=False))
    print(f"\nRelatório: {path}")


if __name__ == "__main__":
    main()
