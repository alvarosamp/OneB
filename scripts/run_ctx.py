"""Executa o teste pré-registrado ctx_v1: o plano padrão paga mais a favor da tendência de 3 meses?

    python scripts/run_ctx.py

Compara DENTRO da mesma direção (compra a favor x compra contra; venda a favor x venda contra).
Relatório em D:/OneB/research/ctx_v1/, resumo em app/research_results/ctx_v1.json.
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
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import calendar_study as cs  # noqa: E402
from app.research_paths import RESEARCH_ROOT  # noqa: E402
from app.setups import load_preregistered  # noqa: E402
from build_trade_plan_rates import HORIZON, h1_atr, load  # noqa: E402

STOP, TARGET = 1.5, 2.0


def per_entry(m5: pd.DataFrame, lo: str, hi: str) -> pd.DataFrame:
    """Resultado em R de cada entrada (compra e venda) do plano padrão, com o contexto conhecido na entrada."""
    atr = h1_atr(m5)
    idx = m5.index
    entries = np.where((idx.minute == 0) & (idx >= pd.Timestamp(lo, tz="UTC")) & (idx < pd.Timestamp(hi, tz="UTC")))[0]
    entries = entries[entries + HORIZON < len(idx)]
    a = atr.reindex(idx[entries], method="ffill").to_numpy()
    ok = np.isfinite(a) & (a > 0)
    entries, a = entries[ok], a[ok]
    span = (idx[entries + HORIZON] - idx[entries]).total_seconds() / 3600
    entries, a = entries[span <= 72], a[span <= 72]
    arr = {k: m5[k].to_numpy() for k in m5.columns}
    # tendência de 3 meses: último dia UTC completo antes da entrada contra 63 pregões antes
    daily = m5["bid_close"].resample("1D").last().dropna()
    trend = (daily / daily.shift(63) - 1)
    day_of_entry = idx[entries].normalize()
    pos = daily.index.searchsorted(day_of_entry, side="left") - 1  # último dia ANTES do dia da entrada
    tr = np.where(pos >= 0, trend.to_numpy()[np.clip(pos, 0, None)], np.nan)
    out = []
    for direction in ("long", "short"):
        entry = arr["ask_open"][entries] if direction == "long" else arr["bid_open"][entries]
        stop_dist = STOP * a
        result = np.full(len(entries), np.nan)
        open_ = np.ones(len(entries), dtype=bool)
        for step in range(HORIZON):
            j = entries + step
            if direction == "long":
                hit_stop = arr["bid_low"][j] <= entry - stop_dist
                hit_tp = arr["bid_high"][j] >= entry + TARGET * stop_dist
            else:
                hit_stop = arr["ask_high"][j] >= entry + stop_dist
                hit_tp = arr["ask_low"][j] <= entry - TARGET * stop_dist
            s_now = open_ & hit_stop
            t_now = open_ & hit_tp & ~hit_stop
            result[s_now], result[t_now] = -1.0, TARGET
            open_ &= ~(s_now | t_now)
            if not open_.any():
                break
        last = entries + HORIZON
        exit_px = arr["bid_close"][last] if direction == "long" else arr["ask_close"][last]
        pnl = (exit_px - entry) if direction == "long" else (entry - exit_px)
        result[open_] = (pnl / stop_dist)[open_]
        sign = 1 if direction == "long" else -1
        out.append(pd.DataFrame({"t": idx[entries], "direction": direction, "r": result,
                                 "aligned": np.sign(tr) * sign > 0, "trend_known": np.isfinite(tr)}))
    df = pd.concat(out, ignore_index=True)
    df = df[df["trend_known"]].drop(columns="trend_known")
    df["day"] = df["t"].dt.tz_convert("America/New_York").dt.date
    df["ny_hour"] = df["t"].dt.tz_convert("America/New_York").dt.hour
    return df


def effect(df: pd.DataFrame) -> float:
    parts = []
    for d in ("long", "short"):
        g = df[df["direction"] == d]
        parts.append(g.loc[g["aligned"], "r"].mean() - g.loc[~g["aligned"], "r"].mean())
    return float(np.mean(parts))


def bootstrap_effect(df: pd.DataFrame, resamples: int = 5000, seed: int = 7, alpha: float = 0.025) -> tuple[float, float]:
    """IC por reamostragem de dias inteiros, com somas por grupo pré-calculadas."""
    days = pd.Index(sorted(df["day"].unique()))
    di = days.get_indexer(df["day"])
    groups = {}
    for d in ("long", "short"):
        for al in (True, False):
            m = ((df["direction"] == d) & (df["aligned"] == al)).to_numpy()
            groups[(d, al)] = (np.bincount(di[m], weights=df["r"].to_numpy()[m], minlength=len(days)),
                               np.bincount(di[m], minlength=len(days)).astype(float))
    rng = np.random.default_rng(seed)
    out = np.empty(resamples)
    for i in range(resamples):
        pick = rng.integers(0, len(days), len(days))
        parts = []
        for d in ("long", "short"):
            (sa, ca), (sc, cc) = groups[(d, True)], groups[(d, False)]
            parts.append(sa[pick].sum() / max(ca[pick].sum(), 1) - sc[pick].sum() / max(cc[pick].sum(), 1))
        out[i] = np.mean(parts)
    return float(np.quantile(out, alpha)), float(np.quantile(out, 1 - alpha))


def describe(df: pd.DataFrame) -> dict:
    rows = {}
    for d in ("long", "short"):
        for al in (True, False):
            g = df[(df["direction"] == d) & (df["aligned"] == al)]
            rows[f"{d}_{'a_favor' if al else 'contra'}"] = {"n": int(len(g)), "mean_r": round(float(g["r"].mean()), 4),
                                                             "p_target": round(float((g["r"] == TARGET).mean()), 4)}
    return rows


def main() -> None:
    spec, sha = load_preregistered("ctx_v1")
    events = cs.load_events(ROOT / "configs" / "events" / "macro_events_2019_2026.json")
    event_days = {t.tz_convert(cs.NEW_YORK).date() for k, t in events if k in ("CPI", "NFP", "FOMC")}
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "test": "ctx_v1", "spec_sha256": sha, "assets": {}}
    for asset in spec["data"]["assets"]:
        m5 = load(asset)
        res = {}
        for phase in ("discovery", "confirmation"):
            per = spec["split"][phase]
            df = per_entry(m5, per["from_inclusive"], per["to_exclusive"])
            lo, hi = bootstrap_effect(df)
            ev = df["day"].isin(event_days)
            res[phase] = {"entries": int(len(df)), "effect_r": round(effect(df), 4), "ci975": [round(lo, 4), round(hi, 4)],
                          "groups": describe(df),
                          "event_days_mean_r": round(float(df.loc[ev, "r"].mean()), 4), "other_days_mean_r": round(float(df.loc[~ev, "r"].mean()), 4),
                          "event_days_p_target": round(float((df.loc[ev, "r"] == TARGET).mean()), 4),
                          "other_days_p_target": round(float((df.loc[~ev, "r"] == TARGET).mean()), 4)}
            print(asset, phase, json.dumps({k: res[phase][k] for k in ("entries", "effect_r", "ci975")}), json.dumps(res[phase]["groups"]), flush=True)
        conf = res["confirmation"]
        passed = (res["discovery"]["ci975"][0] > 0 and conf["ci975"][0] > 0
                  and conf["groups"]["long_a_favor"]["mean_r"] > 0 and conf["groups"]["short_a_favor"]["mean_r"] > 0)
        res["status"] = "PASSED" if passed else "NOT_PASSED"
        report["assets"][asset] = res
    out = RESEARCH_ROOT / "ctx_v1"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"ctx_v1_{datetime.now(timezone.utc):%Y%m%d}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (ROOT / "app" / "research_results" / "ctx_v1.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print({a: v["status"] for a, v in report["assets"].items()})


if __name__ == "__main__":
    main()
