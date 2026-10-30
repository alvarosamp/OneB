"""Notícias como evento: reação a resultados (earnings), dias de choque e manchetes atuais."""
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yfinance as yf

from app.research import features, store

from app.research.universe import STOCKS
UNIVERSE = STOCKS
COST = 0.002  # ida e volta
data = {s: store.load(s) for s in UNIVERSE}


def tstat(x, base):
    x = np.asarray(x)
    if len(x) < 5:
        return None
    se = np.sqrt(x.var(ddof=1) / len(x) + np.var(base, ddof=1) / len(base))
    return round(float((x.mean() - np.mean(base)) / se), 2)


def fwd_from_open(d, i, h):
    """Compra na abertura de i+1, vende na abertura de i+1+h (i = barra do sinal)."""
    if i + 1 + h >= len(d):
        return np.nan
    return d["open"].iloc[i + 1 + h] / d["open"].iloc[i + 1] - 1


# ---------------- A) Earnings ----------------
rows = []
for sym, d in data.items():
    try:
        ed = yf.Ticker(sym).get_earnings_dates(limit=60)
    except Exception:
        continue
    ed = ed.dropna(subset=["Reported EPS"])
    for ts, r in ed.iterrows():
        dt = ts.tz_localize(None) if ts.tzinfo else ts
        day = dt.normalize()
        after_close = dt.hour >= 15
        pos = d.index.searchsorted(day)
        if after_close:
            pos += 1 if (pos < len(d) and d.index[pos] == day) else 0
        if pos < 2 or pos >= len(d) - 1 or d.index[pos] < day:
            continue
        react = d["close"].iloc[pos] / d["close"].iloc[pos - 1] - 1
        row = dict(symbol=sym, date=d.index[pos], react=react, gap=d["open"].iloc[pos] / d["close"].iloc[pos - 1] - 1,
                   surprise=r["Surprise(%)"],
                   pre5=d["close"].iloc[pos - 1] / d["close"].iloc[max(pos - 6, 0)] - 1)
        for h in (5, 20, 60):
            row[f"f{h}"] = fwd_from_open(d, pos, h)
        rows.append(row)
E = pd.DataFrame(rows)
E = E[E.date >= "2015-12-01"].dropna(subset=["react"])
base = {h: np.concatenate([(d["open"].shift(-(1 + h)) / d["open"].shift(-1) - 1).dropna().to_numpy() for d in data.values()]) for h in (5, 20, 60)}
base_mean = {h: v.mean() for h, v in base.items()}
daily_sd = np.mean([d["close"].pct_change().std() for d in data.values()])
print(f"=== A) Resultados trimestrais: {len(E)} eventos em {E.symbol.nunique()} ativos ({E.date.min().date()} a {E.date.max().date()}) ===")
print(f"Movimento médio no dia do resultado: {E.react.abs().mean()*100:.1f}% (dia normal: {daily_sd*100*0.8:.1f}%) → {E.react.abs().mean()/(daily_sd*0.8):.1f}x")
print(f"Surpresa média de EPS: {E.surprise.mean():.1f}%; {100*(E.surprise>0).mean():.0f}% batem a estimativa; preço sobe no dia em {100*(E.react>0).mean():.0f}% dos casos")
print(f"Beat mas preço cai >2%: {((E.surprise>0)&(E.react<-0.02)).mean()*100:.0f}% dos eventos")
print(f"Correlação surpresa x reação do dia: {E.surprise.clip(-50,50).corr(E.react):.2f}")


def group_report(title, mask):
    g = E[mask]
    print(f"\n{title}: n={len(g)}")
    for h in (5, 20, 60):
        x = g[f"f{h}"].dropna()
        if len(x) < 5:
            continue
        ex = x.mean() - base_mean[h]
        net = x.mean() - COST
        print(f"   {h:>2}d após: média {x.mean()*100:6.2f}% (base {base_mean[h]*100:5.2f}%) excesso {ex*100:6.2f}% t={tstat(x, base[h])} acerto {100*(x>0).mean():.0f}%  líquido de custo {net*100:.2f}%")


print("\n--- Efeito 'deriva pós-resultado' (comprar na abertura seguinte à reação) ---")
group_report("Reação > +5%", E.react > 0.05)
group_report("Reação +2% a +5%", (E.react > 0.02) & (E.react <= 0.05))
group_report("Reação entre -2% e +2%", E.react.abs() <= 0.02)
group_report("Reação -5% a -2%", (E.react < -0.02) & (E.react >= -0.05))
group_report("Reação < -5%", E.react < -0.05)
group_report("Surpresa EPS > +10% E reação > +3% (notícia boa confirmada)", (E.surprise > 10) & (E.react > 0.03))
group_report("Surpresa EPS > +5% mas preço caiu > 2% (notícia boa ignorada)", (E.surprise > 5) & (E.react < -0.02))
group_report("Surpresa EPS < -5% e reação < -3% (notícia ruim confirmada)", (E.surprise < -5) & (E.react < -0.03))
train, test = E.date <= "2020-12-31", E.date > "2020-12-31"
print("\n--- Estabilidade treino/teste do efeito 'reação > +5%' ---")
group_report("treino ≤2020", (E.react > 0.05) & train)
group_report("teste 2021+", (E.react > 0.05) & test)
print("\n--- Risco de segurar durante o resultado ---")
print(f"Pior queda no dia: {E.react.min()*100:.1f}%; 5º percentil: {E.react.quantile(.05)*100:.1f}%; 95º: {E.react.quantile(.95)*100:.1f}%")
E.to_csv("output/research/earnings_events.csv", index=False)

# ---------------- B) Dias de choque (volume + preço anormais, fora de earnings) ----------------
earn_days = set(zip(E.symbol, E.date))
ev = []
for sym, d in data.items():
    c, v = d["close"], d["volume"]
    ret = c.pct_change()
    z = ret / ret.rolling(60).std().shift(1)
    vr = v / v.rolling(20).mean().shift(1)
    cand = (z.abs() > 3) & (vr > 2.5)
    last = -10
    for i in np.flatnonzero(cand.to_numpy()):
        if i - last <= 5 or i < 70 or (sym, d.index[i]) in earn_days:
            continue
        last = i
        ev.append(dict(symbol=sym, date=d.index[i], up=ret.iloc[i] > 0, **{f"f{h}": fwd_from_open(d, i, h) for h in (1, 5, 20)}))
S = pd.DataFrame(ev)
b1 = np.concatenate([(d["open"].shift(-2) / d["open"].shift(-1) - 1).dropna().to_numpy() for d in data.values()])
baseS = {1: b1, 5: base[5], 20: base[20]}
print(f"\n=== B) Dias de choque sem resultado (|z|>3 e volume>2,5x): {len(S)} eventos ===")
for name, m in (("Choque de ALTA", S.up), ("Choque de QUEDA", ~S.up)):
    g = S[m]
    print(f"{name}: n={len(g)}")
    for h in (1, 5, 20):
        x = g[f"f{h}"].dropna()
        print(f"   {h:>2}d após: média {x.mean()*100:6.2f}% (base {baseS[h].mean()*100:5.2f}%) excesso {(x.mean()-baseS[h].mean())*100:6.2f}% t={tstat(x, baseS[h])} acerto {100*(x>0).mean():.0f}%")

# ---------------- C) Manchetes atuais (coleta para base futura) ----------------
from app.market_data import rss_news

heads = []
for sym in UNIVERSE:
    for a in rss_news.get_company_news(sym, limit=10):
        heads.append(dict(symbol=sym, published_at=a.published_at.isoformat(), source=a.source, headline=a.headline))
H = pd.DataFrame(heads)
Path("data/news").mkdir(parents=True, exist_ok=True)
if len(H):
    out = Path("data/news") / f"{datetime.now(timezone.utc):%Y-%m-%d}.csv"
    H.drop_duplicates(["symbol", "headline"]).to_csv(out, index=False)
    print(f"\n=== C) {len(H)} manchetes coletadas ({H.symbol.nunique()} ativos) → {out} ===")
    mv = {s: d["close"].iloc[-1] / d["close"].iloc[-6] - 1 for s, d in data.items()}
    for s in sorted(mv, key=lambda k: -abs(mv[k]))[:6]:
        print(f"\n{s}  (5d: {mv[s]*100:+.1f}%)")
        for t in H[H.symbol == s].sort_values("published_at", ascending=False).headline.head(5):
            print("   -", t[:140])
else:
    print("\n=== C) RSS não retornou manchetes agora ===")
