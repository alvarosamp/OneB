"""Estudo de saídas e robustez de parâmetros (RSI2 em tendência de alta e golden cross)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from research_strategies import UNIVERSE, evaluate
from app.research import store, strategies

data = {s: store.load(s) for s in UNIVERSE}


def show(title, variants, factory):
    print(f"\n### {title}")
    print(f"{'variante':34} | {'treino CAGR/Sharpe/DD':>24} | {'teste CAGR/Sharpe/DD':>24} | trades teste | win% | méd%")
    for label, kw in variants.items():
        res, _ = evaluate(factory, data, kw)
        a, b = res["treino 2014-2020"], res["teste 2021-2026"]
        f = lambda m: f"{m['cagr_pct']:>5}/{m['sharpe']:>5}/{m['max_dd_pct']:>6}"
        print(f"{label:34} | {f(a):>24} | {f(b):>24} | {b['trades']:>12} | {b['win_rate_pct']:>4} | {b['avg_trade_pct']}")


show("Saídas para entrada 'RSI2<10 em alta'", {
    "sai RSI2>50": dict(high=50),
    "sai RSI2>70 (base)": dict(high=70),
    "sai RSI2>90": dict(high=90),
    "tempo 3 dias": dict(high=101, max_hold=3),
    "tempo 5 dias": dict(high=101, max_hold=5),
    "tempo 10 dias": dict(high=101, max_hold=10),
    "RSI2>70 + stop 5%": dict(high=70, stop_pct=0.05),
    "RSI2>70 + stop 8%": dict(high=70, stop_pct=0.08),
    "RSI2>70 + trailing 3 ATR": dict(high=70, trail_mult=3),
}, strategies.rsi2_trend)

show("Robustez do limiar de entrada RSI2 (sai >70)", {f"entra RSI2<{x}": dict(low=x) for x in (3, 5, 10, 15, 20, 30)}, strategies.rsi2_trend)
show("Robustez do filtro de tendência (RSI2<10)", {f"filtro SMA{x}": dict(trend=x) for x in (50, 100, 150, 200)}, strategies.rsi2_trend)
show("Golden cross: janelas", {f"{f}/{s}": dict(fast=f, slow=s) for f, s in ((20, 100), (50, 100), (50, 200), (100, 200), (50, 250))}, strategies.golden_cross)
show("Tendência preço>SMA: janela", {f"SMA{n}": dict(n=n) for n in (50, 100, 150, 200, 250)}, strategies.trend_sma)
