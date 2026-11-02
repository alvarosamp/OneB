"""Rodada 2 — hipóteses definidas ANTES de olhar os resultados (poucas, com base na literatura):

H1  Filtro de regime: índice (SPY/QQQ) acima da SMA200 -> investido; senão -> caixa (SHY).
H2  Volatilidade-alvo: reduzir exposição quando a vol realizada sobe (alvo 15% a.a.).
H3  Momentum dual em ETFs: todo mês, top-3 por momentum 12-1 que tenham momentum > 0; resto em caixa.
H4  Momentum em ações (top-10 12-1, mensal), com e sem o filtro de regime H1 no QQQ.

Execução na abertura do dia seguinte, 10 bps por lado de giro. Treino <=2020, teste 2021+.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from app.research import lab, store
from app.research.universe import CASH_PROXY, ETF_UNIVERSE, STOCKS

COST = lab.DEFAULT_COST
SPLIT = "2020-12-31"
PER = {"treino": (None, SPLIT), "teste": ("2021-01-01", None), "completo": (None, None)}
rng = np.random.default_rng(7)

names = list(dict.fromkeys(STOCKS + ETF_UNIVERSE + ["QQQ", "SPY", CASH_PROXY]))
D = {s: store.load(s) for s in names}
idx = D["SPY"].index
OO = pd.DataFrame({s: lab.open_to_open(d) for s, d in D.items()}).reindex(idx).fillna(0.0)
CL = pd.DataFrame({s: d["close"] for s, d in D.items()}).reindex(idx)
CASH = OO[CASH_PROXY]


def port(W: pd.DataFrame) -> pd.Series:
    """W[t] = pesos desejados após o fechamento de t -> executa na abertura de t+1."""
    held = W.reindex(OO.columns, axis=1).fillna(0.0).shift(1).fillna(0.0)
    ret = (held * OO).sum(axis=1) - held.diff().abs().sum(axis=1).fillna(0.0) * COST
    return ret.iloc[:-1]  # última barra não tem abertura seguinte


def month_ends():
    s = pd.Series(idx, index=idx)
    return set(s.groupby([idx.year, idx.month]).last())


def weights_from_scores(pick_fn):
    rb, rows = month_ends(), {}
    cur = pd.Series(0.0, index=OO.columns)
    for t in idx:
        if t in rb:
            cur = pick_fn(t)
        rows[t] = cur
    return pd.DataFrame(rows).T


def mom(universe, t, skip=21, look=252):
    c = CL[universe]
    i = c.index.get_loc(t)
    if i < look:
        return pd.Series(dtype=float)
    return (c.iloc[i - skip] / c.iloc[i - look] - 1).dropna()


def regime_on(t, sym="QQQ", n=200):
    c = CL[sym]
    i = c.index.get_loc(t)
    return i >= n and c.iloc[i] > c.iloc[i - n + 1 : i + 1].mean()


# ---- benchmarks ----
R = {}
R["SPY comprar e segurar"] = port(pd.DataFrame({"SPY": 1.0}, index=idx))
R["QQQ comprar e segurar"] = port(pd.DataFrame({"QQQ": 1.0}, index=idx))
R["Ações (30) igual-peso, seguro"] = port(pd.DataFrame({s: 1 / len(STOCKS) for s in STOCKS}, index=idx))
R["ETFs (15) igual-peso, seguro"] = port(pd.DataFrame({s: 1 / len(ETF_UNIVERSE) for s in ETF_UNIVERSE}, index=idx))

# ---- H1 ----
for sym in ("SPY", "QQQ"):
    for n in (100, 200):
        on = pd.Series([regime_on(t, sym, n) for t in idx], index=idx)
        W = pd.DataFrame({sym: on.astype(float), CASH_PROXY: (~on).astype(float)})
        R[f"H1 {sym} > SMA{n} (senão caixa)"] = port(W)

# ---- H2 ----
def vol_target(r: pd.Series, target=0.15):
    vol = r.rolling(20).std() * np.sqrt(252)
    ex = (target / vol).clip(upper=1.0).shift(1).fillna(0.0)
    c = CASH.reindex(r.index).fillna(0.0)
    return ex * r + (1 - ex) * c - ex.diff().abs().fillna(0.0) * COST


R["H2 QQQ com vol-alvo 15%"] = vol_target(R["QQQ comprar e segurar"])
R["H2 Ações igual-peso com vol-alvo 15%"] = vol_target(R["Ações (30) igual-peso, seguro"])

# ---- H3 ----
def pick_etf(t, top=3):
    m = mom(ETF_UNIVERSE, t)
    m = m[m > 0].nlargest(top)
    w = pd.Series(0.0, index=OO.columns)
    w[m.index] = 1 / top
    w[CASH_PROXY] = 1 - w.sum()
    return w


R["H3 Momentum dual ETFs (top-3)"] = port(weights_from_scores(pick_etf))

# ---- H4 ----
def pick_stocks(t, top=10, gate=False):
    w = pd.Series(0.0, index=OO.columns)
    if gate and not regime_on(t):
        w[CASH_PROXY] = 1.0
        return w
    m = mom(STOCKS, t).nlargest(top)
    if len(m) == 0:
        w[CASH_PROXY] = 1.0
        return w
    w[m.index] = 1 / top
    w[CASH_PROXY] = 1 - w.sum()
    return w


R["H4 Ações top-10 momentum"] = port(weights_from_scores(lambda t: pick_stocks(t)))
R["H4 Ações top-10 momentum + filtro QQQ"] = port(weights_from_scores(lambda t: pick_stocks(t, gate=True)))
R["H2+H4 momentum+filtro+vol-alvo"] = vol_target(R["H4 Ações top-10 momentum + filtro QQQ"])


# ---- relatório ----
def sharpe(x):
    return x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else 0.0


def boot_diff(a: pd.Series, b: pd.Series, block=21, reps=1000):
    df = pd.concat([a, b], axis=1).dropna().to_numpy()
    n = len(df)
    nb = int(np.ceil(n / block))
    out = np.empty(reps)
    for k in range(reps):
        starts = rng.integers(0, n - block, nb)
        samp = np.concatenate([df[s : s + block] for s in starts])[:n]
        out[k] = sharpe(pd.Series(samp[:, 0])) - sharpe(pd.Series(samp[:, 1]))
    return np.percentile(out, [5, 95])


def fmt(m):
    return f"{m.get('cagr_pct', 0):>6.1f} {m.get('sharpe', 0):>5.2f} {m.get('max_dd_pct', 0):>7.1f}"


print(f"{'':44}|{'TREINO ≤2020':^21}|{'TESTE 2021+':^21}|{'COMPLETO':^21}")
print(f"{'estratégia':44}| CAGR%  Shrp  MaxDD% | CAGR%  Shrp  MaxDD% | CAGR%  Shrp  MaxDD%")
for name, r in R.items():
    cells = [fmt(lab.metrics(lab.slice_period(r, a, b))) for a, b in PER.values()]
    print(f"{name:44}| " + " | ".join(cells))

print("\nDiferença de Sharpe vs. referência (intervalo 90% por bootstrap em blocos; só vale se o intervalo não inclui 0):")
pairs = [
    ("H1 QQQ > SMA200 (senão caixa)", "QQQ comprar e segurar"),
    ("H1 SPY > SMA200 (senão caixa)", "SPY comprar e segurar"),
    ("H2 QQQ com vol-alvo 15%", "QQQ comprar e segurar"),
    ("H3 Momentum dual ETFs (top-3)", "ETFs (15) igual-peso, seguro"),
    ("H3 Momentum dual ETFs (top-3)", "SPY comprar e segurar"),
    ("H4 Ações top-10 momentum", "Ações (30) igual-peso, seguro"),
    ("H4 Ações top-10 momentum + filtro QQQ", "Ações (30) igual-peso, seguro"),
    ("H2+H4 momentum+filtro+vol-alvo", "Ações (30) igual-peso, seguro"),
]
for a, b in pairs:
    for pname in ("teste", "completo"):
        lo, hi = PER[pname]
        ra, rb_ = lab.slice_period(R[a], lo, hi), lab.slice_period(R[b], lo, hi)
        ci = boot_diff(ra, rb_)
        d = sharpe(ra.reindex(rb_.index).dropna()) - sharpe(rb_.reindex(ra.index).dropna())
        flag = "✔" if (ci[0] > 0 or ci[1] < 0) else "·"
        print(f"  {a:40} vs {b:32} [{pname:8}] ΔSharpe {d:+.2f}  IC90 [{ci[0]:+.2f}, {ci[1]:+.2f}] {flag}")

print("\nRetorno por ano (%):")
SHOW = {
    "QQQ comprar e segurar": "QQQ B&H",
    "H1 QQQ > SMA200 (senão caixa)": "QQQ>SMA200",
    "H3 Momentum dual ETFs (top-3)": "ETFs dualmom",
    "Ações (30) igual-peso, seguro": "Ações EW",
    "H4 Ações top-10 momentum + filtro QQQ": "Mom+filtro",
    "H2+H4 momentum+filtro+vol-alvo": "Mom+filtro+vol",
}
yr = pd.DataFrame({lbl: (1 + R[k]).groupby(R[k].index.year).prod() - 1 for k, lbl in SHOW.items()}) * 100
print(yr.round(1).to_string())
pd.concat({k: v for k, v in R.items()}, axis=1).to_csv("output/research/rodada2_retornos.csv")
