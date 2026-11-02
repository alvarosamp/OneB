"""Compras/vendas de insiders (Form 4) → retorno futuro ajustado ao mercado (SPY).

Hipóteses fixadas antes de olhar:
 H1 compra relevante: diretor/executivo compra >= US$50k em mercado aberto (1 sinal por ativo a cada 30 dias)
 H2 compras em grupo: >= 3 insiders diferentes comprando em 30 dias
 H3 compra de CEO/CFO >= US$100k
 H4 vendas em grupo: >= 3 insiders vendendo >= US$1M cada em 30 dias (maioria é plano/diversificação: espera-se ~nulo)
Entrada: abertura do pregão seguinte à DATA DE DIVULGAÇÃO. Retorno em 20/60/120 dias menos o do SPY no mesmo período.
Universo = ativos com mais compras (critério só de contagem de eventos) e com preço no yfinance → vivos hoje
(viés de sobrevivência: favorece os resultados de insiders; tratar como teto).
t com erro-padrão agrupado por mês; 4 grupos × 3 horizontes = 12 testes → exigir |t| > ~2.8.
"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from app.research import insiders, store

PRICES = Path("data/history_insiders")
SPLIT = pd.Timestamp("2020-12-31")
HZ = (20, 60, 120)
MIN_PRICE, MIN_DOLLAR_VOL = 5.0, 5e6

ins = insiders.load_all()
ins = ins[(ins.filing_date >= "2015-01-01") & ins.symbol.str.fullmatch(r"[A-Z]{1,5}", na=False)]
ins["value"] = ins.shares * ins.price
ins["is_exec_dir"] = ins.relationship.fillna("").str.contains("Officer|Director", case=False)
ins["is_ceo_cfo"] = ins.title.fillna("").str.contains(r"\bCEO\b|Chief Exec|\bCFO\b|Chief Financial|President", case=False)
buys = ins[(ins.code == "P") & ins.is_exec_dir & (ins.value >= 50_000)]
sells = ins[(ins.code == "S") & ins.is_exec_dir & (ins.value >= 1_000_000)]
print(f"transações no arquivo: {len(ins):,} | compras relevantes: {len(buys):,} em {buys.symbol.nunique()} ativos | vendas >=1M: {len(sells):,}")


def cooldown(df, days=30):
    df = df.sort_values(["symbol", "filing_date"])
    keep, last = [], {}
    for i, r in zip(df.index, df.itertuples()):
        if r.symbol in last and (r.filing_date - last[r.symbol]).days < days:
            continue
        last[r.symbol] = r.filing_date
        keep.append(i)
    return df.loc[keep]


def cluster_signals(df, min_owners=3, window=30):
    """Data em que o N-ésimo insider distinto compra/vende dentro de `window` dias."""
    out = []
    for sym, g in df.sort_values("filing_date").groupby("symbol"):
        d, o = g.filing_date.to_numpy(), g.owner.to_numpy()
        last = None
        for i in range(len(g)):
            lo = d[i] - np.timedelta64(window, "D")
            owners = set(o[(d >= lo) & (d <= d[i])])
            if len(owners) >= min_owners and (last is None or (pd.Timestamp(d[i]) - last).days >= window):
                out.append((sym, pd.Timestamp(d[i])))
                last = pd.Timestamp(d[i])
    return pd.DataFrame(out, columns=["symbol", "filing_date"])


G = {
    "H1 compra >= $50k": cooldown(buys)[["symbol", "filing_date"]],
    "H2 3+ insiders comprando": cluster_signals(buys),
    "H3 CEO/CFO compra >= $100k": cooldown(buys[buys.is_ceo_cfo & (buys.value >= 100_000)])[["symbol", "filing_date"]],
    "H4 3+ insiders vendendo >= $1M": cluster_signals(sells),
}
for k, v in G.items():
    print(f"  {k}: {len(v)} sinais em {v.symbol.nunique()} ativos")

# universo de preços: ativos com mais sinais de compra (contagem, não retorno)
want = pd.concat([G["H1 compra >= $50k"], G["H2 3+ insiders comprando"], G["H3 CEO/CFO compra >= $100k"], G["H4 3+ insiders vendendo >= $1M"]]).symbol.value_counts()
cands = list(want.head(260).index)
spy = store.load("SPY")
data = {}
for s in cands:
    d = store.load(s, PRICES)
    if d.empty:
        try:
            d = store.update(s, PRICES, initial_period="12y")
        except Exception:
            continue
    if len(d) >= 500:
        data[s] = d
print(f"preços disponíveis: {len(data)} de {len(cands)} ativos (os demais saíram do mercado/sem dados → viés de sobrevivência)")


def fwd(d, pos, h):
    if pos + 1 + h >= len(d):
        return np.nan
    return d["open"].iloc[pos + 1 + h] / d["open"].iloc[pos + 1] - 1


rows = []
for grp, sig in G.items():
    for r in sig.itertuples():
        d = data.get(r.symbol)
        if d is None:
            continue
        pos = d.index.searchsorted(r.filing_date.normalize(), side="right") - 1
        if pos < 25 or pos + 1 >= len(d):
            continue
        px = d["close"].iloc[pos]
        dv = (d["close"] * d["volume"]).iloc[pos - 20 : pos].mean()
        if px < MIN_PRICE or dv < MIN_DOLLAR_VOL:
            continue
        sp = spy.index.searchsorted(d.index[pos], side="right") - 1
        row = dict(group=grp, symbol=r.symbol, date=d.index[pos], dv=dv)
        for h in HZ:
            a, b = fwd(d, pos, h), fwd(spy, sp, h)
            row[f"x{h}"] = a - b
        rows.append(row)
E = pd.DataFrame(rows)
E["month"] = E.date.dt.to_period("M")


def clustered(x, months):
    x = pd.Series(x.to_numpy(), index=months.to_numpy())
    n = len(x)
    se = np.sqrt((x.groupby(level=0).sum() ** 2).sum()) / n
    return x.mean(), (x.mean() / se if se > 0 else np.nan)


print(f"\neventos com preço/liquidez válidos: {len(E)}  (preço >= ${MIN_PRICE:.0f}, volume financeiro 20d >= ${MIN_DOLLAR_VOL/1e6:.0f}M)\n")
print(f"{'grupo':32}{'n':>5} | " + " | ".join(f"{'+'+str(h)+'d vs SPY':^24}" for h in HZ) + " | t(120d) treino/teste")
for grp in G:
    g = E[E.group == grp]
    if len(g) < 10:
        print(f"{grp:32}{len(g):>5} | poucos eventos")
        continue
    cells = []
    for h in HZ:
        x = g[f"x{h}"].dropna()
        m, t = clustered(x, g.loc[x.index, "month"])
        cells.append(f"{m*100:>6.2f}% t={t:>5.2f} ac{(x>0).mean()*100:>3.0f}%")
    tt = []
    for sub in (g[g.date <= SPLIT], g[g.date > SPLIT]):
        x = sub["x120"].dropna()
        tt.append(clustered(x, sub.loc[x.index, "month"])[1] if len(x) > 15 else np.nan)
    print(f"{grp:32}{len(g):>5} | " + " | ".join(cells) + f" | {tt[0]:>5.2f} / {tt[1]:>5.2f}")

# separa megacaps (liquidez alta) de small/mid
print("\nPor liquidez (H1+H2, 60d vs SPY):")
g = E[E.group.isin(["H1 compra >= $50k", "H2 3+ insiders comprando"])]
for lbl, m in (("volume < $20M/dia (small)", g.dv < 2e7), ("$20M–$200M/dia (mid)", (g.dv >= 2e7) & (g.dv < 2e8)), ("> $200M/dia (large)", g.dv >= 2e8)):
    s = g[m]
    x = s["x60"].dropna()
    if len(x) >= 10:
        mm, t = clustered(x, s.loc[x.index, "month"])
        print(f"  {lbl:28} n={len(s):>4}  {mm*100:>6.2f}%  t={t:>5.2f}")
E.drop(columns="month").to_csv("output/research/insiders_eventos.csv", index=False)
