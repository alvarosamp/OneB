"""Executa o teste pré-registrado tom_v1 (virada do mês nos índices).

    python scripts/run_tom.py

Relatório em D:/OneB/research/tom_v1/, resumo versionado em app/research_results/tom_v1.json.
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

SLIPPAGE = 0.0002
FINANCING = 0.02


def tom_flags(index: pd.DatetimeIndex) -> pd.Series:
    """True no último pregão do mês e nos 3 primeiros do mês seguinte."""
    s = pd.Series(index, index=index)
    month = index.to_period("M")
    pos = s.groupby(month).cumcount()
    rev = s.groupby(month).cumcount(ascending=False)
    return pd.Series((pos <= 2).to_numpy() | (rev == 0).to_numpy(), index=index)


def diff_ci(ret: pd.Series, flag: pd.Series, resamples: int = 10_000, seed: int = 7) -> tuple[float, float, float]:
    """Média TOM - média resto, com IC por bootstrap de meses inteiros."""
    month = ret.index.to_period("M")
    groups = [(g.to_numpy(), flag.loc[g.index].to_numpy()) for _, g in ret.groupby(month)]
    point = float(ret[flag].mean() - ret[~flag].mean())
    rng = np.random.default_rng(seed)
    out = np.empty(resamples)
    for i in range(resamples):
        pick = rng.integers(0, len(groups), size=len(groups))
        r = np.concatenate([groups[k][0] for k in pick])
        f = np.concatenate([groups[k][1] for k in pick])
        out[i] = r[f].mean() - r[~f].mean()
    return point, float(np.quantile(out, 0.025)), float(np.quantile(out, 0.975))


def strategy_monthly(close: pd.Series, spread_rel: float) -> pd.Series:
    """Comprado do fechamento do dia -2 ao fechamento do dia +3; um valor por mês (o mês novo)."""
    idx = close.index
    month = idx.to_period("M")
    firsts = pd.Series(range(len(idx)), index=idx).groupby(month).min()
    out = {}
    for m, i_first in firsts.items():
        i_entry, i_exit = i_first - 2, i_first + 2  # fechamento de -2 até fechamento de +3
        if i_entry < 0 or i_exit >= len(idx):
            continue
        gross = close.iloc[i_exit] / close.iloc[i_entry] - 1
        days = (idx[i_exit] - idx[i_entry]).days
        cost = spread_rel + 2 * SLIPPAGE + FINANCING * days / 365
        out[m] = gross - cost
    return pd.Series(out)


def analyse(inst: str, period: dict, recent: dict) -> dict:
    frame = trend.load_daily(inst)
    close = frame["close"]
    spread = frame["spread"][frame["spread"] > 0]
    spread_rel = float((spread / close.loc[spread.index]).median()) if len(spread) else 0.0
    ret = close.pct_change().dropna()
    flag = tom_flags(close.index).loc[ret.index]
    lo, hi = pd.Timestamp(period["from_inclusive"]), pd.Timestamp(period["to_exclusive"])
    mask = (ret.index >= lo) & (ret.index < hi)
    r, f = ret[mask], flag[mask]
    point, c_lo, c_hi = diff_ci(r, f)
    strat = strategy_monthly(close, spread_rel)
    strat = strat[(strat.index >= pd.Period(lo, "M")) & (strat.index < pd.Period(hi, "M"))]
    s_lo, s_hi = trend.ci(strat.to_numpy(), block=12)
    rlo, rhi = pd.Timestamp(recent["from_inclusive"]), pd.Timestamp(recent["to_exclusive"])
    rmask = (r.index >= rlo) & (r.index < rhi)
    recent_diff = float(r[rmask & f.to_numpy()].mean() - r[rmask & ~f.to_numpy()].mean())
    share = float(((1 + r[f]).prod() - 1) / ((1 + r).prod() - 1)) if (1 + r).prod() != 1 else None
    by_year = {str(y): round(float(g[f.loc[g.index]].mean() - g[~f.loc[g.index]].mean()) * 1e4, 1) for y, g in r.groupby(r.index.year)}
    return {
        "days": int(len(r)), "tom_days": int(f.sum()),
        "tom_mean_bps": round(float(r[f].mean()) * 1e4, 2), "other_mean_bps": round(float(r[~f].mean()) * 1e4, 2),
        "diff_bps": round(point * 1e4, 2), "diff_ci95_bps": [round(c_lo * 1e4, 2), round(c_hi * 1e4, 2)],
        "strategy_months": int(len(strat)), "strategy_mean_monthly": round(float(strat.mean()), 5),
        "strategy_ci95": [round(s_lo, 5), round(s_hi, 5)], "strategy_cost_per_month_est": round(spread_rel + 2 * SLIPPAGE + FINANCING * 5 / 365, 5),
        "recent_diff_bps": round(recent_diff * 1e4, 2), "share_of_total_return_from_tom": round(share, 3) if share is not None else None,
        "diff_by_year_bps": by_year,
    }


def main() -> None:
    spec, sha = load_preregistered("tom_v1")
    period, recent = spec["data"]["period"], spec["data"]["recent_window"]
    primary_inst = "usa500idxusd"
    primary = analyse(primary_inst, period, recent)
    secondary = {}
    for inst in spec["data"]["secondary_assets"]:
        try:
            secondary[inst] = analyse(inst, period, recent)
        except FileNotFoundError:
            secondary[inst] = {"error": "sem dados"}
    h1 = primary["diff_ci95_bps"][0] > 0
    h2 = primary["strategy_ci95"][0] > 0
    passed = h1 and h2 and primary["recent_diff_bps"] > 0
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "test": "tom_v1", "spec_sha256": sha,
              "status": "PASSED" if passed else "NOT_PASSED", "H1": h1, "H2": h2, "primary_asset": primary_inst,
              "primary": primary, "secondary": secondary}
    out = RESEARCH_ROOT / "tom_v1"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"tom_v1_{datetime.now(timezone.utc):%Y%m%d}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (ROOT / "app" / "research_results" / "tom_v1.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("status", "H1", "H2")}, indent=1))
    print("S&P 500:", json.dumps({k: v for k, v in primary.items() if k != "diff_by_year_bps"}))
    print("por ano (bps):", primary["diff_by_year_bps"])
    for k, v in secondary.items():
        print(k, {x: v.get(x) for x in ("diff_bps", "diff_ci95_bps", "strategy_mean_monthly", "strategy_ci95", "recent_diff_bps")})


if __name__ == "__main__":
    main()
