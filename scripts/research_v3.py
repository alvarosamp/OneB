"""Rodada 3 — dados novos. Hipóteses fixadas antes de ver resultados.

A) Contexto macro/risco (VIX, estrutura a termo, crédito, curva, condições financeiras, dólar, juros):
   o estado do mercado hoje muda o retorno futuro do QQQ/SPY (5 e 21 dias)?
B) Revisões de analistas (upgrade, downgrade, preço-alvo) nas 30 ações: há deriva depois do evento?
Erros-padrão: Newey-West (A) e agrupados por mês (B). Com 14 testes em A, exigir |t| > ~2.9.
"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from app.research import external, lab, store
from app.research.universe import STOCKS

M = external.MACRO_DIR
SPLIT = pd.Timestamp("2020-12-31")


def fwd_ret(d, h):
    o = d["open"]
    return o.shift(-(1 + h)) / o.shift(-1) - 1


def nw_ols(y: np.ndarray, x: np.ndarray, lags: int):
    """OLS y = a + b x com erro-padrão Newey-West. Retorna (b, t)."""
    if min(x.sum(), len(x) - x.sum()) < 30:  # poucos dias em um dos estados: estimativa sem sentido
        return np.nan, np.nan
    X = np.column_stack([np.ones(len(x)), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    u = y - X @ beta
    Xu = X * u[:, None]
    S = Xu.T @ Xu / len(y)
    for L in range(1, lags + 1):
        G = Xu[L:].T @ Xu[:-L] / len(y)
        S += (1 - L / (lags + 1)) * (G + G.T)
    XtXi = np.linalg.inv(X.T @ X / len(y))
    V = XtXi @ S @ XtXi / len(y)
    return beta[1], beta[1] / np.sqrt(V[1, 1])


# ---------------- A) macro ----------------
vix, vix3m, vvix = (store.load(s, M)["close"] for s in ("^VIX", "^VIX3M", "^VVIX"))
dxy, tnx = store.load("DX-Y.NYB", M)["close"], store.load("^TNX", M)["close"]
hyg, lqd = store.load("HYG", M)["close"], store.load("LQD", M)["close"]
t10 = external.load_fred("T10Y2Y", M)
nfci = external.load_fred("NFCI", M)
base = store.load("QQQ")
idx = base.index


def al(s, lag=0):
    return s.reindex(idx.union(s.index)).ffill().reindex(idx).shift(lag)


pct = lambda s, w=252: s.rolling(w, min_periods=120).apply(lambda a: (a[:-1] < a[-1]).mean(), raw=True)
credit = al(hyg / lqd)
CONDS = {
    "VIX em backwardation (VIX/VIX3M > 1)": (al(vix) / al(vix3m)) > 1,
    "VIX acima do percentil 80 (252d)": pct(al(vix)) > 0.8,
    "VVIX acima do percentil 80 (252d)": pct(al(vvix)) > 0.8,
    "Estresse de crédito (HYG/LQD cai 20d, pior quintil)": (credit.pct_change(20)) < credit.pct_change(20).rolling(252, min_periods=120).quantile(0.2),
    "Curva invertida (10a-2a < 0, defasada 1d)": al(t10, 1) < 0,
    "Condições financeiras apertadas (NFCI > 0, defasada 7d)": al(nfci, 7) > 0,
    "Dólar forte (DXY 60d > 0)": al(dxy).pct_change(60) > 0,
    "Juros subindo (TNX 20d > 0)": al(tnx).pct_change(20) > 0,
}
print("=== A) Contexto macro → retorno futuro do índice (diferença: condição verdadeira menos falsa) ===")
print("limiar de significância com 16 testes (Bonferroni 5%): |t| ≈ 2.9\n")
for tgt in ("QQQ", "SPY"):
    d = store.load(tgt)
    print(f"--- {tgt} ---")
    print(f"{'condição':56}{'h':>3} {'%dias':>6} {'ret|V':>7} {'ret|F':>7} {'Δ%':>6} {'t(NW)':>6} | {'t treino':>8} {'t teste':>8} {'vol|V':>6} {'vol|F':>6}")
    for name, cond in CONDS.items():
        for h in (5, 21):
            y = fwd_ret(d, h)
            df = pd.DataFrame({"y": y, "c": cond.reindex(d.index).astype(float)}).dropna()
            b, t = nw_ols(df.y.to_numpy(), df.c.to_numpy(), h)
            parts = []
            for sub in (df[df.index <= SPLIT], df[df.index > SPLIT]):
                parts.append(nw_ols(sub.y.to_numpy(), sub.c.to_numpy(), h)[1])
            v, f = df[df.c == 1].y, df[df.c == 0].y
            print(f"{name:56}{h:>3} {df.c.mean()*100:>5.0f}% {v.mean()*100:>6.2f}% {f.mean()*100:>6.2f}% {b*100:>6.2f} {t:>6.2f} | {parts[0]:>8.2f} {parts[1]:>8.2f} {v.std()*100:>5.1f}% {f.std()*100:>5.1f}%")
    print()

# ---------------- B) analistas ----------------
rows = []
for s in STOCKS:
    a = external.load_analysts(s)
    d = store.load(s)
    if a.empty or d.empty:
        continue
    fw = {h: fwd_ret(d, h) for h in (1, 5, 20)}
    mu = {h: fw[h].mean() for h in fw}
    a = a[a.index >= "2013-01-01"]
    pt_chg = (a["currentPriceTarget"] / a["priorPriceTarget"].replace(0, np.nan) - 1)
    for ts, r, chg in zip(a.index, a.itertuples(), pt_chg):
        pos = d.index.searchsorted(ts.normalize(), side="right") - 1
        if pos < 0 or pos + 1 >= len(d):
            continue
        g = []
        if r.Action == "up": g.append("Upgrade")
        if r.Action == "down": g.append("Downgrade")
        if r.priceTargetAction == "Raises": g.append("Alvo sobe")
        if r.priceTargetAction == "Lowers": g.append("Alvo cai")
        if chg == chg and chg >= 0.15: g.append("Alvo sobe >=15%")
        if chg == chg and chg <= -0.10: g.append("Alvo cai >=10%")
        for grp in g:
            rows.append(dict(symbol=s, date=d.index[pos], group=grp, **{f"x{h}": fw[h].iloc[pos] - mu[h] for h in fw}))
E = pd.DataFrame(rows)
E = E.sort_values(["symbol", "group", "date"])
keep = []
last = {}
for i, r in zip(E.index, E.itertuples()):  # carência de 3 dias por ativo/grupo (evita contar o mesmo evento várias vezes)
    k = (r.symbol, r.group)
    if k in last and (r.date - last[k]).days <= 3:
        continue
    last[k] = r.date
    keep.append(i)
E = E.loc[keep]
E["month"] = E.date.dt.to_period("M")


def clustered(x, months):
    x = pd.Series(x.to_numpy(), index=months.to_numpy())
    n = len(x)
    cs = x.groupby(level=0).sum()
    se = np.sqrt((cs ** 2).sum()) / n
    return x.mean(), x.mean() / se if se > 0 else np.nan


print(f"=== B) Revisões de analistas: excesso de retorno vs. média do próprio ativo (entrada na abertura seguinte), {len(E)} eventos ===")
print("t com erro-padrão agrupado por mês; 6 grupos × 3 horizontes = 18 testes → exigir |t| > ~2.9\n")
print(f"{'grupo':18}{'n':>6} | " + " | ".join(f"{'h='+str(h)+'d':^22}" for h in (1, 5, 20)) + " | t treino/teste (20d)")
for grp in ["Upgrade", "Downgrade", "Alvo sobe", "Alvo cai", "Alvo sobe >=15%", "Alvo cai >=10%"]:
    g = E[E.group == grp]
    cells = []
    for h in (1, 5, 20):
        x = g[f"x{h}"].dropna()
        m, t = clustered(x, g.loc[x.index, "month"])
        cells.append(f"{m*100:>6.2f}% t={t:>5.2f} ac{(x>0).mean()*100:>3.0f}%")
    tt = []
    for sub in (g[g.date <= SPLIT], g[g.date > SPLIT]):
        x = sub["x20"].dropna()
        tt.append(clustered(x, sub.loc[x.index, "month"])[1] if len(x) > 10 else np.nan)
    print(f"{grp:18}{len(g):>6} | " + " | ".join(cells) + f" | {tt[0]:>5.2f} / {tt[1]:>5.2f}")
E.drop(columns="month").to_csv("output/research/analistas_eventos.csv", index=False)
