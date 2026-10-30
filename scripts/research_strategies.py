"""Backtest das regras clássicas em ~32 ativos, treino vs. teste. Uso: python scripts/research_strategies.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from app.research import lab, store, strategies

from app.research.universe import STOCKS
UNIVERSE = STOCKS
SPLIT = "2020-12-31"
PERIODS = {"completo": (None, None), "treino 2014-2020": (None, SPLIT), "teste 2021-2026": ("2021-01-01", None)}


def run_rule(rule, d, cost=lab.DEFAULT_COST):
    entry = rule.entry.reindex(d.index).fillna(False).to_numpy(bool)
    exit_ = rule.exit.reindex(d.index).fillna(False).to_numpy(bool) if rule.exit is not None else None
    kw = dict(rule.kwargs)
    a = strategies.atr(d).to_numpy() if "trail_mult" in kw else None
    pos = pd.Series(lab.simulate_position(entry, exit_, d["close"].to_numpy(), atr=a, **kw), index=d.index)
    return pos, lab.strategy_returns(pos, d, cost)


def evaluate(factory, data, label_kwargs=None):
    """Retorna {periodo: métricas} da carteira igual-peso + estatísticas de trades agregadas."""
    rets, trades, expo = {}, {p: [] for p in PERIODS}, {p: [] for p in PERIODS}
    per_asset = {}
    for sym, d in data.items():
        rule = factory(d, **(label_kwargs or {}))
        pos, r = run_rule(rule, d)
        rets[sym] = r
        per_asset[sym] = (pos, r)
    R = pd.DataFrame(rets)
    out = {}
    for pname, (a, b) in PERIODS.items():
        sub = lab.slice_period(R, a, b)
        port = lab.equal_weight(sub)
        tr, ex = [], []
        for sym, (pos, r) in per_asset.items():
            rr = lab.slice_period(r, a, b)
            if len(rr) < 20:
                continue
            tr += lab.trade_returns(pos.loc[rr.index], rr)
            ex.append(float(pos.shift(1).fillna(0).loc[rr.index].mean()))
        out[pname] = lab.metrics(port, tr, float(np.mean(ex)) if ex else None)
    return out, R


def main():
    data = {s: store.load(s) for s in UNIVERSE}
    results = {}
    for name, factory in strategies.STRATEGIES.items():
        results[name], _ = evaluate(factory, data)
    qqq = store.load("QQQ")
    q = lab.strategy_returns(pd.Series(1.0, index=qqq.index), qqq, cost=0)
    results["QQQ (referência)"] = {p: lab.metrics(lab.slice_period(q, a, b)) for p, (a, b) in PERIODS.items()}
    Path("output/research").mkdir(parents=True, exist_ok=True)
    Path("output/research/strategies.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    for pname in PERIODS:
        print(f"\n=== {pname} ===")
        print(f"{'estratégia':38} {'CAGR%':>7} {'Sharpe':>6} {'MaxDD%':>7} {'expos%':>6} {'trades':>6} {'win%':>5} {'méd%':>6} {'PF':>5}")
        for name, res in results.items():
            m = res[pname]
            print(f"{name:38} {m.get('cagr_pct',''):>7} {m.get('sharpe',''):>6} {m.get('max_dd_pct',''):>7} {m.get('exposure_pct',''):>6} {m.get('trades',''):>6} {m.get('win_rate_pct',''):>5} {m.get('avg_trade_pct',''):>6} {str(m.get('profit_factor','')):>5}")


if __name__ == "__main__":
    main()
