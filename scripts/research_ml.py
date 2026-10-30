"""IC dos indicadores + ML walk-forward (LR, gradient boosting, rede neural) com simulação de carteira."""
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.research import features, lab, store

UNIVERSE = [p.stem for p in sorted(Path("data/history").glob("*.csv")) if p.stem not in ("QQQ", "SPY", "GC_F", "BRL_X")]
H = features.HORIZON
K = 5
SPLIT = pd.Timestamp("2020-12-31")

data = {s: store.load(s) for s in UNIVERSE}
panel = features.build_panel(data, store.load("QQQ"), H)
FEATS = [c for c in panel.columns if c not in ("fwd", "fwd_rel")]
panel = panel.dropna(subset=FEATS + ["fwd"])
X_all = features.rank_normalize(panel, FEATS)
dates = panel.index.get_level_values("date").unique().sort_values()
print(f"painel: {len(panel)} linhas, {len(UNIVERSE)} ativos, {dates[0].date()} a {dates[-1].date()}, {len(FEATS)} features")


# ---------- 1) Qualidade de cada indicador (IC por data, amostrando a cada H dias p/ não sobrepor) ----------
def ic_table(sub_dates):
    rows = []
    sample = sub_dates[::H]
    for f in FEATS:
        ics, spreads = [], []
        for dt in sample:
            x = X_all[f].xs(dt, level="date")
            y = panel["fwd"].xs(dt, level="date")
            if len(x) < 15:
                continue
            ics.append(x.corr(y.rank(), method="pearson"))
            q = x.rank(pct=True)
            spreads.append(y[q > 0.8].mean() - y[q <= 0.2].mean())
        ics, spreads = np.array(ics), np.array(spreads)
        rows.append({
            "feature": f,
            "IC": ics.mean(),
            "t": ics.mean() / ics.std(ddof=1) * np.sqrt(len(ics)),
            "spread_Q5-Q1_pct": spreads.mean() * 100,
        })
    return pd.DataFrame(rows).set_index("feature")


tr_dates, te_dates = dates[dates <= SPLIT], dates[dates > SPLIT]
ic_tr, ic_te = ic_table(tr_dates), ic_table(te_dates)
ic = ic_tr.join(ic_te, lsuffix="_treino", rsuffix="_teste")
ic["consistente"] = np.sign(ic["IC_treino"]) == np.sign(ic["IC_teste"])
ic = ic.reindex(ic["t_treino"].abs().sort_values(ascending=False).index)
pd.set_option("display.width", 200)
print("\n=== Poder preditivo de cada indicador (retorno relativo em 5 dias; IC>0 = valor alto → bom) ===")
print(ic.round(3).to_string())

# ---------- 2) ML walk-forward ----------
def models():
    return {
        "Regressão logística": make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=300)),
        "Gradient boosting": HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, l2_regularization=1.0, random_state=0),
        "Rede neural (MLP 32-16)": make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(32, 16), alpha=1e-2, early_stopping=True, max_iter=200, random_state=0)),
    }


y_bin = (panel["fwd_rel"] > 0).astype(int)
test_years = list(range(2019, dates[-1].year + 1))
preds = {m: pd.Series(np.nan, index=panel.index) for m in models()}
perm_acc = {}
for yr in test_years:
    t0, t1 = pd.Timestamp(f"{yr}-01-01"), pd.Timestamp(f"{yr}-12-31")
    cut = dates[dates < t0][-(H + 5)] if (dates < t0).sum() > H + 5 else None
    dd = panel.index.get_level_values("date")
    tr_mask = dd <= cut
    te_mask = (dd >= t0) & (dd <= t1)
    if te_mask.sum() == 0 or tr_mask.sum() < 5000:
        continue
    for name, model in models().items():
        model.fit(X_all[tr_mask], y_bin[tr_mask])
        preds[name][te_mask] = model.predict_proba(X_all[te_mask])[:, 1]
        if name == "Gradient boosting":
            sub = np.random.default_rng(0).choice(np.flatnonzero(te_mask), size=min(6000, te_mask.sum()), replace=False)
            pi = permutation_importance(model, X_all.iloc[sub], y_bin.iloc[sub], scoring="roc_auc", n_repeats=3, random_state=0)
            for f, v in zip(FEATS, pi.importances_mean):
                perm_acc.setdefault(f, []).append(v)
    print(f"  fold {yr} ok", flush=True)

oos = panel.index[preds["Regressão logística"].notna()]
print(f"\nOut-of-sample: {oos.get_level_values('date').min().date()} a {oos.get_level_values('date').max().date()} ({len(oos)} linhas)")


def backtest_topk(score: pd.Series, label: str, cost=lab.DEFAULT_COST):
    s = score.dropna()
    rb = s.index.get_level_values("date").unique().sort_values()[::H]
    prev, rets, bench, turns = set(), [], [], []
    for dt in rb:
        cs = s.xs(dt, level="date")
        fw = panel["fwd"].xs(dt, level="date").reindex(cs.index)
        if len(cs) < K * 2:
            continue
        sel = set(cs.nlargest(K).index)
        turn = 1 - len(sel & prev) / K if prev else 1.0
        rets.append(fw[list(sel)].mean() - 2 * cost * turn)
        turns.append(turn)
        bench.append(fw.mean())
        prev = sel
    r, b = pd.Series(rets), pd.Series(bench)
    ann = 252 / H
    def stats(x):
        eq = (1 + x).cumprod()
        yrs = len(x) / ann
        return dict(cagr=round((eq.iloc[-1] ** (1 / yrs) - 1) * 100, 1), sharpe=round(x.mean() / x.std() * np.sqrt(ann), 2),
                    dd=round((eq / eq.cummax() - 1).min() * 100, 1), hit=round((x > 0).mean() * 100, 1))
    st = stats(r)
    st['giro_pct'] = round(float(np.mean(turns)) * 100, 0)
    return st, stats(b), r


results = {}
print("\n=== Modelos fora da amostra (2019-2026), carteira top-5 rebalanceada a cada 5 dias ===")
base_stats = None
for name, p in preds.items():
    pm = p.dropna()
    auc = roc_auc_score(y_bin[pm.index], pm)
    ic_pred = np.mean([pm.xs(dt, level="date").corr(panel["fwd"].xs(dt, level="date").reindex(pm.xs(dt, level="date").index), method="spearman")
                       for dt in pm.index.get_level_values("date").unique()[::H]])
    st, bench, _ = backtest_topk(p, name)
    gross = backtest_topk(p, name, cost=0)[0]
    base_stats = bench
    results[name] = dict(auc=round(auc, 4), ic=round(ic_pred, 4), bruto_cagr=gross['cagr'], bruto_sharpe=gross['sharpe'], **st)
    print(f"{name:28} {auc:6.3f} {ic_pred:6.3f} | liq {st['cagr']:>5}% Sh {st['sharpe']:>5} DD {st['dd']:>6} | bruto {gross['cagr']:>5}% Sh {gross['sharpe']:>5} | giro {st['giro_pct']:.0f}%")

# baselines: aleatório e momentum puro
rng = np.random.default_rng(1)
rand_stats = []
oos_idx = panel.index[preds["Regressão logística"].notna()]
for i in range(100):
    sc = pd.Series(rng.random(len(oos_idx)), index=oos_idx)
    rand_stats.append(backtest_topk(sc, "rand")[0])
rand_df = pd.DataFrame(rand_stats)
rg = [backtest_topk(pd.Series(rng.random(len(oos_idx)), index=oos_idx), "r", cost=0)[0] for _ in range(30)]
rg = pd.DataFrame(rg)
print(f"{'Sorteio aleatório (média 100x)':28} {'0.500':>6} {'0.000':>6} | liq {rand_df.cagr.mean():>5.1f}% Sh {rand_df.sharpe.mean():>5.2f} DD {rand_df.dd.mean():>6.1f} | bruto {rg.cagr.mean():>5.1f}% Sh {rg.sharpe.mean():>5.2f} | giro {rand_df.giro_pct.mean():.0f}%")
print(f"  (desvio do sorteio: CAGR ±{rand_df.cagr.std():.1f}, Sharpe ±{rand_df.sharpe.std():.2f}; melhor dos 100: Sharpe {rand_df.sharpe.max():.2f})")
mom = backtest_topk(X_all["mom_12_1"].reindex(oos_idx), "mom")[0]
momg = backtest_topk(X_all["mom_12_1"].reindex(oos_idx), "mom", cost=0)[0]
print(f"{'Momentum 12-1 (top-5)':28} {'-':>6} {'-':>6} | liq {mom['cagr']:>5}% Sh {mom['sharpe']:>5} DD {mom['dd']:>6} | bruto {momg['cagr']:>5}% Sh {momg['sharpe']:>5} | giro {mom['giro_pct']:.0f}%")
print(f"{'Todos igual-peso (sem custo)':28} {'-':>6} {'-':>6} | liq {base_stats['cagr']:>5}% Sh {base_stats['sharpe']:>5} DD {base_stats['dd']:>6}")

imp = pd.Series({f: np.mean(v) for f, v in perm_acc.items()}).sort_values(ascending=False)
print("\n=== Importância (gradient boosting, queda de AUC ao embaralhar; fora da amostra) ===")
print((imp.head(8) * 1000).round(2).to_string(), "(x1e-3)")

Path("output/research").mkdir(parents=True, exist_ok=True)
ic.round(4).to_csv("output/research/ic_indicadores.csv")
json.dump({"modelos": results, "aleatorio": rand_df.mean().round(2).to_dict(), "momentum": mom, "igual_peso": base_stats},
          open("output/research/ml.json", "w"), indent=1)
