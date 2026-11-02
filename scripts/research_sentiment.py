"""Sentimento das manchetes x retorno seguinte (excesso sobre a média das 30 ações).

Entrada na abertura do primeiro pregão após a publicação (nada de olhar à frente), saída h pregões
depois. Com poucas semanas de arquivo o teste é só um piloto: o script imprime n e t para deixar
claro quando ainda não há poder estatístico. Uso: python scripts/research_sentiment.py [--no-llm]
"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from app.research import news_archive, sentiment, store
from app.research.universe import STOCKS

use_llm = "--no-llm" not in sys.argv
HORIZONS = (1, 3, 5)

archive = news_archive.load()
archive = archive[archive["symbol"].isin(STOCKS)]
scores = sentiment.score_archive(archive, use_llm=use_llm)
print(f"manchetes no arquivo: {len(archive)} | relevantes pontuadas: {len(scores)} | com LLM: {int(scores['llm'].notna().sum())}")

data = {s: store.load(s) for s in STOCKS}
opens = pd.DataFrame({s: d["open"] for s, d in data.items()}).sort_index()

pub = archive.drop_duplicates(["symbol", "headline"]).merge(scores, on=["symbol", "headline"])
pub["ts"] = pd.to_datetime(pub["published_at"], utc=True, errors="coerce").dt.tz_convert("America/New_York")
pub = pub.dropna(subset=["ts"])

idx = opens.index
open_ts = (idx + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York")
pub["entry_pos"] = np.searchsorted(open_ts.values, pub["ts"].values, side="right")  # 1º open depois da notícia

rows = []
for r in pub.itertuples():
    for h in HORIZONS:
        i, j = r.entry_pos, r.entry_pos + h
        if j >= len(idx) or pd.isna(opens[r.symbol].iloc[i]) or pd.isna(opens[r.symbol].iloc[j]):
            continue
        own = opens[r.symbol].iloc[j] / opens[r.symbol].iloc[i] - 1
        mkt = (opens.iloc[j] / opens.iloc[i] - 1).mean()
        rows.append(dict(symbol=r.symbol, day=idx[i], h=h, lexicon=r.lexicon, llm=r.llm, excess=own - mkt))
ev = pd.DataFrame(rows)
if ev.empty:
    print("Ainda não há manchetes com retorno futuro disponível.")
    sys.exit()

print("\nExcesso de retorno (% sobre a média das 30 ações) por sinal do sentimento")
print(f"{'fonte':8s} {'h':>2s} {'grupo':9s} {'n':>5s} {'média%':>8s} {'t':>6s}")
out = []
for src in ("lexicon", "llm"):
    d = ev.dropna(subset=[src])
    for h in HORIZONS:
        x = d[d["h"] == h]
        for name, mask in (("positivo", x[src] > 0), ("neutro", x[src] == 0), ("negativo", x[src] < 0)):
            g = x[mask]["excess"]
            if len(g) < 2:
                continue
            # erro-padrão agrupado por dia: manchetes do mesmo dia compartilham o mesmo choque de mercado
            daily = x[mask].groupby("day")["excess"].mean()
            t = daily.mean() / (daily.std(ddof=1) / np.sqrt(len(daily))) if len(daily) > 2 else float("nan")
            print(f"{src:8s} {h:2d} {name:9s} {len(g):5d} {g.mean()*100:8.2f} {t:6.2f}")
            out.append(dict(source=src, h=h, group=name, n=len(g), mean_excess_pct=g.mean() * 100, t=t))
        if x[src].nunique() > 2:
            print(f"{src:8s} {h:2d} correlação sentimento x excesso: {x[src].corr(x['excess']):.3f} (n={len(x)})")

print(f"\ndias distintos com sinal: {ev['day'].nunique()} (precisa de meses para conclusão)")
Path("output/research").mkdir(parents=True, exist_ok=True)
pd.DataFrame(out).to_csv("output/research/sentimento_eventos.csv", index=False)
