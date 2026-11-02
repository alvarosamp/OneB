"""Pesquisa ouro (GC=F / XAUUSD MT5) e Nasdaq (NQ=F / QQQ): varredura de indicadores, redes neurais walk-forward e efeitos intradiários.

Protocolo (o mesmo das rodadas anteriores):
- sinal no fechamento de t, posição a partir do retorno de t+1; dados cruzados e macro defasados 1 dia;
- treino até 2020, teste 2021+; walk-forward anual com expurgo (purge) de h dias entre treino e teste;
- custo de 3 bps por lado no diário; spread real do MT5 no H1;
- critério de "achado": |t| > 2,8 no treino E mesmo sinal com |t| > 2 no teste.

Rode antes: python scripts/fetch_gold_nasdaq.py
"""
import json
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import torch
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "research" / "gold_nasdaq"
OUT = ROOT / "output" / "research" / "ouro_nasdaq"
OUT.mkdir(parents=True, exist_ok=True)

SPLIT = pd.Timestamp("2020-12-31")
COST = 0.0003  # 3 bps por lado
HORIZONS = [1, 5, 20]
RNG = np.random.default_rng(7)
torch.set_num_threads(4)
FAST = "--fast" in sys.argv  # sem LSTM, para iterar rápido
results: dict = {}


def d1(name):
    return pd.read_csv(D / f"d1_{name}.csv", index_col=0, parse_dates=True)


# ---------------------------------------------------------------- features diárias
def rsi(c, n):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def zscore(s, n=252):
    return (s - s.rolling(n).mean()) / s.rolling(n).std()


def build(target):
    px = d1(target)
    c, h, l = px.close, px.high, px.low
    idx = c.index
    lr = np.log(c).diff()
    f = pd.DataFrame(index=idx)
    for n in (1, 5, 20, 60, 120, 250):
        f[f"ret_{n}"] = np.log(c / c.shift(n))
    f["mom_12_1"] = f["ret_250"] - f["ret_20"]
    for n in (20, 50, 200):
        f[f"sma{n}_dist"] = c / c.rolling(n).mean() - 1
    f["rsi14"], f["rsi2"] = rsi(c, 14), rsi(c, 2)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    f["atr14_pct"] = tr.rolling(14).mean() / c
    f["vol20"], f["vol60"] = lr.rolling(20).std(), lr.rolling(60).std()
    f["vol_ratio"] = f["vol20"] / f["vol60"]
    f["boll_z"] = (c - c.rolling(20).mean()) / c.rolling(20).std()
    macd = c.ewm(span=12).mean() - c.ewm(span=26).mean()
    f["macd_hist"] = (macd - macd.ewm(span=9).mean()) / c
    f["donch55_pos"] = (c - l.rolling(55).min()) / (h.rolling(55).max() - l.rolling(55).min())
    f["range_pct"] = (h - l) / c
    f["dow"] = idx.dayofweek
    m = pd.Series(idx.month, index=idx)
    f["tom"] = (m != m.shift(-1)).astype(int) | (m != m.shift(1)).astype(int) | (m != m.shift(2)).astype(int)

    # dados cruzados: alinhados ao calendário do alvo e defasados 1 dia (horários de fechamento diferentes)
    other = "nq" if target == "gold" else "gold"
    cross = {}
    for name in ["dxy", "tnx", "spx", "silver", "copper", "oil", "usdjpy", "hyg", "ief", other]:
        oc = d1(name).close.reindex(idx, method="ffill")
        for n in (1, 5, 20):
            cross[f"{name}_ret{n}"] = np.log(oc / oc.shift(n))
    vix = d1("vix").close.reindex(idx, method="ffill")
    vix3m = d1("vix3m").close.reindex(idx, method="ffill")
    cross["vix_z"] = zscore(vix)
    cross["vix_term"] = vix / vix3m
    cross["vix_chg5"] = np.log(vix / vix.shift(5))
    gold_c = d1("gold").close.reindex(idx, method="ffill")
    cross["gold_silver_z"] = zscore(gold_c / d1("silver").close.reindex(idx, method="ffill"))
    cross["copper_gold_z"] = zscore(d1("copper").close.reindex(idx, method="ffill") / gold_c)
    # NFCI é semanal: preencher antes de alinhar. O spread HY do FRED só tem ~3 anos (licença ICE); HYG cobre crédito.
    fred = pd.read_csv(D / "fred.csv", index_col=0, parse_dates=True).ffill().reindex(idx, method="ffill")
    cross["real10"] = fred["DFII10"]
    cross["real10_chg5"], cross["real10_chg20"] = fred["DFII10"].diff(5), fred["DFII10"].diff(20)
    cross["be10_chg20"] = fred["T10YIE"].diff(20)
    cross["curve_10y2y"] = fred["T10Y2Y"]
    cross["nfci"] = fred["NFCI"]
    cross = pd.DataFrame(cross).shift(1)
    f = f.join(cross)

    for hh in HORIZONS:
        f[f"y{hh}"] = np.log(c.shift(-hh) / c)
    f["r_next"] = lr.shift(-1)
    return f


# ---------------------------------------------------------------- utilidades estatísticas
def t_corr(r, n):
    return r * np.sqrt(max(n - 2, 1) / max(1 - r * r, 1e-9))


def ic_scan(f, feats, target):
    rows = []
    for hh in HORIZONS:
        for col in feats:
            row = {"alvo": target, "h": hh, "feature": col}
            for tag, sub in (("treino", f[f.index <= SPLIT]), ("teste", f[f.index > SPLIT])):
                s = sub[[col, f"y{hh}"]].dropna().iloc[::hh]  # sem sobreposição
                r = stats.spearmanr(s[col], s[f"y{hh}"]).statistic if len(s) > 30 else np.nan
                row[f"ic_{tag}"], row[f"t_{tag}"], row[f"n_{tag}"] = r, t_corr(r, len(s)), len(s)
            row["passa"] = bool(abs(row["t_treino"]) > 2.8 and abs(row["t_teste"]) > 2
                                and np.sign(row["ic_treino"]) == np.sign(row["ic_teste"]))
            rows.append(row)
    return pd.DataFrame(rows)


def perf(pnl, periods=252):
    pnl = pnl.dropna()
    if len(pnl) < 20 or pnl.std() == 0:
        return {"cagr": 0.0, "sharpe": 0.0, "maxdd": 0.0}
    eq = np.exp(pnl.cumsum())
    yrs = len(pnl) / periods
    return {"cagr": round((eq.iloc[-1] ** (1 / yrs) - 1) * 100, 2),
            "sharpe": round(pnl.mean() / pnl.std() * np.sqrt(periods), 3),
            "maxdd": round((eq / eq.cummax() - 1).min() * 100, 1)}


def block_boot_sharpe_diff(a, b, block=20, reps=2000, periods=252):
    """IC 90% da diferença de Sharpe (a - b) por bootstrap em blocos circulares."""
    x = pd.concat([a, b], axis=1).dropna().values
    n = len(x)
    if n < 100:
        return [np.nan, np.nan]
    diffs = []
    for _ in range(reps):
        starts = RNG.integers(0, n, n // block + 1)
        ix = (starts[:, None] + np.arange(block)).ravel()[:n] % n
        s = x[ix]
        sa = s[:, 0].mean() / (s[:, 0].std() + 1e-12)
        sb = s[:, 1].mean() / (s[:, 1].std() + 1e-12)
        diffs.append((sa - sb) * np.sqrt(periods))
    return [round(float(np.percentile(diffs, 5)), 3), round(float(np.percentile(diffs, 95)), 3)]


def auc_shift_pvalue(y, p, reps=500, min_shift=60):
    """p-valor da AUC contra deslocamentos circulares das previsões (preserva autocorrelação)."""
    y, p = np.asarray(y), np.asarray(p)
    n = len(y)
    if n < 2 * min_shift or len(np.unique(y)) < 2:
        return np.nan
    obs = roc_auc_score(y, p)
    null = [roc_auc_score(y, np.roll(p, k)) for k in RNG.integers(min_shift, n - min_shift, reps)]
    return float((np.sum(np.abs(np.array(null) - 0.5) >= abs(obs - 0.5)) + 1) / (reps + 1))


# ---------------------------------------------------------------- modelos
def fit_logit(Xtr, ytr, Xte):
    m = LogisticRegression(C=0.05, max_iter=2000).fit(Xtr, ytr)
    return m.predict_proba(Xte)[:, 1]


def fit_mlp(Xtr, ytr, Xte, seeds=5):
    ps = []
    for s in range(seeds):
        m = MLPClassifier(hidden_layer_sizes=(32, 16), alpha=1e-2, learning_rate_init=1e-3, max_iter=300,
                          early_stopping=True, validation_fraction=0.2, n_iter_no_change=15, random_state=s)
        ps.append(m.fit(Xtr, ytr).predict_proba(Xte)[:, 1])
    return np.mean(ps, axis=0)


class LSTMNet(torch.nn.Module):
    def __init__(self, k, hidden=24):
        super().__init__()
        self.lstm = torch.nn.LSTM(k, hidden, batch_first=True)
        self.drop = torch.nn.Dropout(0.3)
        self.out = torch.nn.Linear(hidden, 1)

    def forward(self, x):
        o, _ = self.lstm(x)
        return self.out(self.drop(o[:, -1])).squeeze(-1)


def make_seq(X, L):
    # X: (n, k) -> (n, L, k), linha i usa X[i-L+1 .. i]; as L-1 primeiras ficam com zeros
    n, k = X.shape
    pad = np.vstack([np.zeros((L - 1, k)), X])
    return np.lib.stride_tricks.sliding_window_view(pad, (L, k))[:, 0]


def fit_lstm(Str, ytr, Ste, seeds=3, epochs=25, L=None):
    ps = []
    for s in range(seeds):
        torch.manual_seed(s)
        net = LSTMNet(Str.shape[2])
        opt = torch.optim.Adam(net.parameters(), lr=2e-3, weight_decay=1e-4)
        nval = int(len(Str) * 0.2)
        xt, yt = torch.tensor(Str[:-nval], dtype=torch.float32), torch.tensor(ytr[:-nval], dtype=torch.float32)
        xv, yv = torch.tensor(Str[-nval:], dtype=torch.float32), torch.tensor(ytr[-nval:], dtype=torch.float32)
        lossf = torch.nn.BCEWithLogitsLoss()
        best, best_state, bad = 1e9, None, 0
        for ep in range(epochs):
            net.train()
            perm = torch.randperm(len(xt))
            for i in range(0, len(xt), 128):
                b = perm[i:i + 128]
                opt.zero_grad()
                lossf(net(xt[b]), yt[b]).backward()
                opt.step()
            net.eval()
            with torch.no_grad():
                vl = lossf(net(xv), yv).item()
            if vl < best - 1e-4:
                best, best_state, bad = vl, {k: v.clone() for k, v in net.state_dict().items()}, 0
            else:
                bad += 1
                if bad >= 5:
                    break
        net.load_state_dict(best_state)
        net.eval()
        with torch.no_grad():
            ps.append(torch.sigmoid(net(torch.tensor(Ste, dtype=torch.float32))).numpy())
    return np.mean(ps, axis=0)


def strategy(sig, r_next, hh, cost=COST):
    """sig em {0,1} (comprado/fora) ou {-1,1}; carteira escalonada: média dos últimos h sinais."""
    pos = sig.rolling(hh, min_periods=1).mean()
    return pos * r_next - cost * pos.diff().abs().fillna(pos.abs())


# ---------------------------------------------------------------- PARTE A+B: diário
def daily_study(target):
    print(f"\n================ {target.upper()} diário ================")
    f = build(target)
    feats = [c for c in f.columns if not c.startswith("y") and c != "r_next"]
    f = f[f.index >= "2001-01-01"]

    ic = ic_scan(f, feats, target)
    ic.to_csv(OUT / f"ic_{target}.csv", index=False)
    top = ic.reindex(ic["t_treino"].abs().sort_values(ascending=False).index).head(12)
    print(top[["h", "feature", "ic_treino", "t_treino", "ic_teste", "t_teste", "passa"]].round(3).to_string(index=False))
    passed = ic[ic["passa"]]
    print(f"passaram no critério: {len(passed)} de {len(ic)} testes")
    res = {"ic_testes": len(ic), "ic_passaram": passed[["h", "feature", "ic_treino", "t_treino", "ic_teste", "t_teste"]]
           .round(4).to_dict("records")}

    # walk-forward: começa em 2008 (VIX3M/HYG existem desde 2006/2007 + aquecimento de 250 dias)
    f = f[f.index >= "2008-06-01"].copy()
    f[feats] = f[feats].ffill()
    f = f.dropna(subset=feats + ["r_next"])
    years = list(range(2012, f.index[-1].year + 1))
    models = ["logit", "mlp"] + ([] if FAST else ["lstm"])
    res["modelos"] = {}
    for hh in HORIZONS:
        preds = {m: pd.Series(np.nan, index=f.index) for m in models}
        for yr in years:
            te = f.index.year == yr
            tr_end = f.index[te][0]
            tr = (f.index < tr_end)
            tr_idx = np.where(tr)[0][:-hh]  # expurgo: rótulo de h dias não pode invadir o teste
            ylab = (f[f"y{hh}"] > 0).astype(int).values
            valid_tr = tr_idx[~np.isnan(f[f"y{hh}"].values[tr_idx])]
            sc = StandardScaler().fit(f[feats].values[valid_tr])
            X = np.clip(sc.transform(f[feats].values), -5, 5)
            te_idx = np.where(te)[0]
            preds["logit"].iloc[te_idx] = fit_logit(X[valid_tr], ylab[valid_tr], X[te_idx])
            preds["mlp"].iloc[te_idx] = fit_mlp(X[valid_tr], ylab[valid_tr], X[te_idx])
            if "lstm" in models:
                S = make_seq(X, 20)
                v = valid_tr[valid_tr >= 19]
                preds["lstm"].iloc[te_idx] = fit_lstm(S[v], ylab[v], S[te_idx])
            print(f"  {target} h={hh} {yr} ok", flush=True)
        out = {}
        bh = f["r_next"]
        for m in models:
            p = preds[m]
            for tag, mask in (("2012-2020", (f.index.year >= 2012) & (f.index <= SPLIT)), ("2021+", f.index > SPLIT)):
                sub = f[mask]
                pm = p[mask]
                yl = sub[f"y{hh}"].notna()
                yb = (sub[f"y{hh}"][yl] > 0).astype(int)
                auc = roc_auc_score(yb, pm[yl])
                pval = auc_shift_pvalue(yb.values, pm[yl].values)
                acc = float(((pm[yl] > 0.5).astype(int) == yb).mean())
                long_flat = strategy((pm > 0.5).astype(float), sub["r_next"], hh)
                long_short = strategy(np.sign(pm - 0.5), sub["r_next"], hh)
                out[f"{m}|{tag}"] = {
                    "auc": round(auc, 4), "p_auc": round(pval, 4), "acerto": round(acc, 4),
                    "taxa_base_alta": round(float(yb.mean()), 4),
                    "comprado_fora": perf(long_flat), "comprado_vendido": perf(long_short),
                    "exposicao": round(float((pm > 0.5).mean()), 3),
                    "ic90_sharpe_vs_bh": block_boot_sharpe_diff(long_flat, sub["r_next"]),
                }
        for tag, mask in (("2012-2020", (f.index.year >= 2012) & (f.index <= SPLIT)), ("2021+", f.index > SPLIT)):
            sub = f[mask]
            out[f"buy_hold|{tag}"] = {"comprado_fora": perf(sub["r_next"])}
            tsm = strategy((sub["ret_250"] > 0).astype(float), sub["r_next"], 1)
            out[f"tendencia_12m|{tag}"] = {"comprado_fora": perf(tsm),
                                           "ic90_sharpe_vs_bh": block_boot_sharpe_diff(tsm, sub["r_next"])}
            s200 = strategy((sub["sma200_dist"] > 0).astype(float), sub["r_next"], 1)
            out[f"sma200|{tag}"] = {"comprado_fora": perf(s200),
                                    "ic90_sharpe_vs_bh": block_boot_sharpe_diff(s200, sub["r_next"])}
        res["modelos"][f"h{hh}"] = out
        print(f"\n-- h={hh}d")
        for k, v in out.items():
            cf = v["comprado_fora"]
            extra = f" AUC={v['auc']:.3f} p={v['p_auc']:.3f} acerto={v['acerto']:.3f} base={v['taxa_base_alta']:.3f}" if "auc" in v else ""
            ci = v.get("ic90_sharpe_vs_bh")
            print(f"{k:24s} CAGR={cf['cagr']:6.2f} Sharpe={cf['sharpe']:5.2f} DD={cf['maxdd']:6.1f}{extra}"
                  + (f" ΔSharpe90%={ci}" if ci else ""))

    # importância por permutação do MLP no teste (h=5), para saber o que a rede usa
    return res


# ---------------------------------------------------------------- PARTE C: ouro H1 (MT5)
def gold_h1_study():
    print("\n================ OURO H1 (MT5 XAUUSD.dk) ================")
    g = pd.read_csv(D / "mt5_XAUUSD_dk_h1.csv", index_col=0, parse_dates=True)
    g = g[~g.index.duplicated()].sort_index()
    spread_frac = (g["spread"] * 0.01 / g["close"]).median()  # spread em pontos de 0,01
    r = np.log(g.close).diff()
    split = pd.Timestamp("2022-12-31")
    res = {"barras": len(g), "inicio": str(g.index[0]), "fim": str(g.index[-1]),
           "spread_bps": round(spread_frac * 1e4, 2)}

    # C1: sazonalidade por hora (horário do servidor da corretora)
    rows = []
    for hr in sorted(g.index.hour.unique()):
        row = {"hora": int(hr)}
        for tag, m in (("treino", r.index <= split), ("teste", r.index > split)):
            x = r[m & (r.index.hour == hr)].dropna()
            row[f"media_bps_{tag}"] = round(x.mean() * 1e4, 2)
            row[f"t_{tag}"] = round(x.mean() / x.std() * np.sqrt(len(x)), 2)
        row["passa"] = bool(abs(row["t_treino"]) > 2.8 and abs(row["t_teste"]) > 2
                            and np.sign(row["t_treino"]) == np.sign(row["t_teste"]))
        rows.append(row)
    hours = pd.DataFrame(rows)
    print(hours.to_string(index=False))
    res["sazonalidade_hora"] = hours.to_dict("records")
    # estratégia: comprado só nas horas com t>2 no treino, testada depois de 2022.
    # A hora de cada barra é conhecida antes, então a posição vale para a própria barra (sem shift).
    good = hours.loc[hours["t_treino"] > 2, "hora"].tolist()
    sig = pd.Series(r.index.hour.isin(good).astype(float), index=r.index)
    pnl = sig * r - spread_frac / 2 * sig.diff().abs().fillna(0)
    te = pnl.index > split
    res["horas_boas_treino"] = good
    res["estrategia_horas_teste_bruta_de_swap"] = perf(pnl[te], periods=252 * 23)
    res["buy_hold_h1_teste"] = perf(r[te], periods=252 * 23)
    print("horas boas no treino:", good, "| teste (sem swap):", res["estrategia_horas_teste_bruta_de_swap"],
          "| B&H:", res["buy_hold_h1_teste"])

    # A hora 1 é a 1ª barra após a pausa diária: segurar a posição atravessa o rollover e paga swap.
    # Teste executável no feed real da corretora (XAUUSD.s): compra no ask às 23h, vende no bid à 1h, ter-sex.
    s = pd.read_csv(D / "mt5_XAUUSD_s_h1.csv", index_col=0, parse_dates=True)
    ok = (s.index.hour == 1) & (s.index.dayofweek > 0) & (pd.Series(s.index.hour, index=s.index).shift(1) == 23).values
    net = np.log(s.close / (s.close.shift(1) + s.spread.shift(1) * 0.01))[ok].dropna()
    swap_bps = 66 * 0.01 * 100 / (s.close.iloc[-1] * 100) * 1e4 * 7 / 5  # 66 pontos/lote/noite, quarta triplo
    res["reabertura_executavel"] = {
        "noites": len(net), "periodo": f"{net.index[0].date()} a {net.index[-1].date()}",
        "liquido_spread_bps": round(net.mean() * 1e4, 2), "t": round(net.mean() / net.std() * np.sqrt(len(net)), 2),
        "swap_medio_bps": round(swap_bps, 2), "liquido_spread_e_swap_bps": round(net.mean() * 1e4 - swap_bps, 2)}
    print("reabertura executável:", res["reabertura_executavel"])

    # C2: redes neurais em H1 — prever direção das próximas 4 h
    H = 4
    feat = pd.DataFrame(index=g.index)
    for n in (1, 2, 4, 8, 24, 72, 120):
        feat[f"ret_{n}"] = np.log(g.close / g.close.shift(n))
    feat["vol24"] = r.rolling(24).std()
    feat["vol120"] = r.rolling(120).std()
    feat["range"] = (g.high - g.low) / g.close
    feat["rng_ratio"] = feat["range"] / feat["range"].rolling(120).mean()
    feat["vol_tick_ratio"] = g.volume / g.volume.rolling(120).mean()
    feat["sma24_dist"] = g.close / g.close.rolling(24).mean() - 1
    feat["sma120_dist"] = g.close / g.close.rolling(120).mean() - 1
    feat["rsi14"] = rsi(g.close, 14)
    feat["hour_sin"] = np.sin(2 * np.pi * g.index.hour / 24)
    feat["hour_cos"] = np.cos(2 * np.pi * g.index.hour / 24)
    feat["dow"] = g.index.dayofweek
    y = np.log(g.close.shift(-H) / g.close)
    df = feat.join(y.rename("y")).join(r.shift(-1).rename("r_next")).dropna()
    feats = list(feat.columns)
    # walk-forward semestral a partir de 2023
    starts = pd.date_range("2023-01-01", df.index[-1], freq="6MS")
    models = ["logit", "mlp"] + ([] if FAST else ["lstm"])
    preds = {m: pd.Series(np.nan, index=df.index) for m in models}
    for st in starts:
        en = st + pd.DateOffset(months=6)
        te_idx = np.where((df.index >= st) & (df.index < en))[0]
        if len(te_idx) == 0:
            continue
        tr_idx = np.where(df.index < st)[0][:-H]
        sc = StandardScaler().fit(df[feats].values[tr_idx])
        X = np.clip(sc.transform(df[feats].values), -5, 5)
        yl = (df["y"].values > 0).astype(int)
        preds["logit"].iloc[te_idx] = fit_logit(X[tr_idx], yl[tr_idx], X[te_idx])
        preds["mlp"].iloc[te_idx] = fit_mlp(X[tr_idx], yl[tr_idx], X[te_idx], seeds=3)
        if "lstm" in models:
            S = make_seq(X, 24)
            v = tr_idx[tr_idx >= 23][-20000:]  # últimas ~3,5 anos de barras para caber na CPU
            preds["lstm"].iloc[te_idx] = fit_lstm(S[v], yl[v], S[te_idx], seeds=2, epochs=15)
    te = df.index >= starts[0]
    sub = df[te]
    res["nn_h1"] = {}
    for m in models:
        p = preds[m][te]
        yb = (sub["y"] > 0).astype(int)
        long_short = np.sign(p - 0.5)
        pos = long_short.rolling(H, min_periods=1).mean()
        pnl = pos * sub["r_next"] - spread_frac / 2 * pos.diff().abs().fillna(1)
        res["nn_h1"][m] = {"auc": round(roc_auc_score(yb, p), 4), "p_auc": round(auc_shift_pvalue(yb.values, p.values), 4),
                           "acerto": round(float(((p > 0.5).astype(int) == yb).mean()), 4),
                           "comprado_vendido_liquido": perf(pnl, periods=252 * 23),
                           "comprado_vendido_bruto": perf(pos * sub["r_next"], periods=252 * 23)}
        print(m, res["nn_h1"][m])
    return res


# ---------------------------------------------------------------- PARTE D: Nasdaq intradiário
def nasdaq_intraday_study():
    print("\n================ NASDAQ intradiário ================")
    res = {}
    # D1: momentum intradiário (Gao, Han, Li e Zhou, 2018) com QQQ 1h, horário de NY
    q = pd.read_csv(D / "qqq_1h_yf.csv", index_col=0, parse_dates=True)
    q.index = q.index.tz_localize("UTC").tz_convert("America/New_York")
    q["day"] = q.index.date
    rows = []
    days = sorted(q["day"].unique())
    prev_close = None
    for dday in days:
        x = q[q["day"] == dday]
        first = x[(x.index.hour == 9) & (x.index.minute == 30)]
        last = x[(x.index.hour == 15) & (x.index.minute == 30)]
        before_last = x[x.index < last.index[0]] if len(last) else None
        if prev_close is not None and len(first) and len(last) and len(before_last):
            rows.append({"day": dday,
                         "r_first": first.close.iloc[0] / prev_close - 1,
                         "r_mid": before_last.close.iloc[-1] / first.close.iloc[0] - 1,
                         "r_last": last.close.iloc[0] / before_last.close.iloc[-1] - 1})
        if len(x):
            prev_close = x.close.iloc[-1]
    im = pd.DataFrame(rows).set_index("day")
    slope, inter, rr, pv, se = stats.linregress(im["r_first"], im["r_last"])
    pnl = np.sign(im["r_first"]) * im["r_last"] - 2 * 0.0001
    res["momentum_intradiario_qqq"] = {
        "dias": len(im), "periodo": f"{im.index[0]} a {im.index[-1]}",
        "beta": round(slope, 4), "t": round(slope / se, 2), "r2_pct": round(rr ** 2 * 100, 2),
        "estrategia_bps_por_dia_liq": round(pnl.mean() * 1e4, 2),
        "t_estrategia": round(pnl.mean() / pnl.std() * np.sqrt(len(pnl)), 2),
        "acerto": round(float((pnl > 0).mean()), 3)}
    print("momentum intradiário QQQ:", res["momentum_intradiario_qqq"])

    # D2: noturno x pregão (QQQ diário desde 2000)
    qd = d1("qqq")
    on = np.log(qd.open / qd.close.shift(1))
    intra = np.log(qd.close / qd.open)
    out = {}
    for tag, m in (("2001-2020", (qd.index.year >= 2001) & (qd.index <= SPLIT)), ("2021+", qd.index > SPLIT)):
        o, i = on[m].dropna(), intra[m].dropna()
        out[tag] = {"noturno_bps_dia": round(o.mean() * 1e4, 2), "t_noturno": round(o.mean() / o.std() * np.sqrt(len(o)), 2),
                    "pregao_bps_dia": round(i.mean() * 1e4, 2), "t_pregao": round(i.mean() / i.std() * np.sqrt(len(i)), 2),
                    "noturno_liq_1bp_lado": perf(o - 0.0002), "so_pregao": perf(i), "buy_hold": perf(o + i)}
    res["noturno_vs_pregao_qqq"] = out
    print("noturno vs pregão:", json.dumps(out, indent=1))

    # D3: dia da semana e virada de mês no NQ (sanity, efeitos famosos de fórum)
    nq = d1("nq").close
    r = np.log(nq).diff().dropna()
    mo = pd.Series(r.index.month, index=r.index)
    tom = (mo != mo.shift(-1)) | (mo != mo.shift(1)) | (mo != mo.shift(2)) | (mo != mo.shift(3))
    cal = {}
    for tag, m in (("2001-2020", r.index <= SPLIT), ("2021+", r.index > SPLIT)):
        a, b = r[m & tom], r[m & ~tom]
        tt = stats.ttest_ind(a, b, equal_var=False)
        cal[tag] = {"virada_mes_bps": round(a.mean() * 1e4, 2), "resto_bps": round(b.mean() * 1e4, 2), "t": round(tt.statistic, 2)}
    res["virada_de_mes_nq"] = cal
    print("virada de mês NQ:", cal)
    return res


if __name__ == "__main__":
    t0 = time.time()
    # partes opcionais: --so=gold_h1,nasdaq_intradiario atualiza só essas chaves do resultados.json
    only = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--so=")), None)
    path = OUT / "resultados.json"
    if only and path.exists():
        results.update(json.loads(path.read_text(encoding="utf-8")))
    parts = {"gold_diario": lambda: daily_study("gold"), "nq_diario": lambda: daily_study("nq"),
             "gold_h1_mt5": gold_h1_study, "nasdaq_intradiario": nasdaq_intraday_study}
    for key, fn in parts.items():
        if only is None or key in only:
            results[key] = fn()
    results["gerado_em"] = pd.Timestamp.now().isoformat()
    path.write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
    print(f"\nok em {time.time() - t0:.0f}s -> {OUT}")
