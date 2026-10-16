"""Executa o replay_v1: um usuário que abre o OneB em vários horários e segue o plano da IA.

    python scripts/run_replay.py

Regras congeladas em configs/preregistration/replay_v1.json (conferidas pelo LOCK).
Resumo versionado em app/research_results/replay_v1.json.
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
sys.path.insert(0, str(ROOT / "scripts"))

from app import calendar_study as cs  # noqa: E402
from app.setups import load_preregistered  # noqa: E402
from build_trade_plan_rates import h1_atr, load  # noqa: E402

HORIZON = 288  # barras M5 = 24 h
SKIP_CLASSES = {"fechado", "evitar", "parado"}
RULES = ("aleatorio", "acompanha_24h", "contra_1h")


def entries_for(m5: pd.DataFrame, slots: list[str], offset_h: int) -> np.ndarray:
    idx = m5.index
    utc_minutes = {((int(s[:2]) - offset_h) * 60 + int(s[3:])) % 1440 for s in slots}
    minute_of_day = idx.hour * 60 + idx.minute
    e = np.where(np.isin(minute_of_day, list(utc_minutes)))[0]
    return e[e + HORIZON < len(idx)]


def simulate(m5: pd.DataFrame, entries: np.ndarray, stop_dist: np.ndarray, target_r: float) -> dict:
    arr = {k: m5[k].to_numpy() for k in m5.columns}
    out = {}
    for direction in ("long", "short"):
        entry = arr["ask_open"][entries] if direction == "long" else arr["bid_open"][entries]
        hit = np.zeros(len(entries), dtype=bool)
        r = np.full(len(entries), np.nan)
        open_ = np.ones(len(entries), dtype=bool)
        for step in range(HORIZON):
            j = entries + step
            if direction == "long":
                hit_stop = arr["bid_low"][j] <= entry - stop_dist
                hit_tp = arr["bid_high"][j] >= entry + target_r * stop_dist
            else:
                hit_stop = arr["ask_high"][j] >= entry + stop_dist
                hit_tp = arr["ask_low"][j] <= entry - target_r * stop_dist
            stop_now = open_ & hit_stop
            tp_now = open_ & hit_tp & ~hit_stop
            r[stop_now] = -1.0
            r[tp_now], hit[tp_now] = target_r, True
            open_ &= ~(stop_now | tp_now)
            if not open_.any():
                break
        last = entries + HORIZON
        exit_px = arr["bid_close"][last] if direction == "long" else arr["ask_close"][last]
        pnl = (exit_px - entry) if direction == "long" else (entry - exit_px)
        r[open_] = (pnl / stop_dist)[open_]
        out[direction] = (r, hit)
    return out


def past_mid(m5: pd.DataFrame, entries: np.ndarray, hours: int) -> np.ndarray:
    """Preço médio (abertura) da última barra disponível 'hours' antes da entrada."""
    idx = m5.index
    mid = ((m5["bid_open"] + m5["ask_open"]) / 2).to_numpy()
    pos = idx.searchsorted(idx[entries] - pd.Timedelta(hours=hours), side="right") - 1
    out = np.where(pos >= 0, mid[np.clip(pos, 0, None)], np.nan)
    return out


def summarize(df: pd.DataFrame, start_balance: float, risk: float) -> dict:
    if df.empty:
        return {"trades": 0}
    df = df.sort_values("time")
    cum = df["r"].cumsum().to_numpy()
    dd = float(np.max(np.maximum.accumulate(np.concatenate([[0.0], cum]))[1:] - cum)) if len(cum) else 0.0
    balance = float(start_balance * np.prod(1 + risk * df["r"].to_numpy()))
    return {"trades": int(len(df)), "p_target": round(float(df["hit"].mean()), 4), "mean_r": round(float(df["r"].mean()), 4),
            "sum_r": round(float(df["r"].sum()), 1), "max_drawdown_r": round(dd, 1), "final_balance": round(balance, 0),
            "spread_r": round(float(df["spread_r"].mean()), 4)}


def bootstrap_ci(diff: pd.Series, days: pd.Series, level: float, reps: int, seed: int) -> tuple[float, float]:
    by_day = pd.DataFrame({"d": diff.to_numpy(), "day": days.to_numpy()}).groupby("day")["d"].agg(["sum", "count"])
    s, c = by_day["sum"].to_numpy(), by_day["count"].to_numpy()
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(s), size=(reps, len(s)))
    means = s[pick].sum(axis=1) / c[pick].sum(axis=1)
    a = (1 - level) / 2
    return float(np.quantile(means, a)), float(np.quantile(means, 1 - a))


def main() -> None:
    spec, sha = load_preregistered("replay_v1")
    plan, data = spec["plan"], spec["data"]
    guide = json.loads((ROOT / "app" / "research_results" / "hours_guide.json").read_text(encoding="utf-8"))
    events = [t for kind, t in cs.load_events(ROOT / "configs" / "events" / "macro_events_2019_2026.json") if kind in {"CPI", "NFP", "FOMC"}]
    ev_times = pd.DatetimeIndex(events)
    periods = {k: (pd.Timestamp(v["from_inclusive"], tz="UTC"), pd.Timestamp(v["to_exclusive"], tz="UTC")) for k, v in spec["split"].items()}
    out = {"test": "replay_v1", "sha256": sha, "generated_at": datetime.now(timezone.utc).isoformat(), "assets": {}}
    n_comp = 2 * len(data["assets"])
    level = 1 - 0.05 / n_comp
    for asset in data["assets"]:
        m5 = load(asset)
        idx = m5.index
        e = entries_for(m5, data["slots_brasilia"], data["brasilia_utc_offset_hours"])
        e = e[(idx[e] >= periods["discovery"][0]) & (idx[e] < periods["confirmation"][1])]
        atr = h1_atr(m5).reindex(idx[e], method="ffill").to_numpy()
        span = (idx[e + HORIZON] - idx[e]).total_seconds() / 3600
        ok = np.isfinite(atr) & (atr > 0) & (span <= 72)
        e, atr = e[ok], atr[ok]
        stop = plan["stop_atr_h1"] * atr
        sim = simulate(m5, e, stop, plan["target_r"])
        t = idx[e]
        mid_now = ((m5["bid_open"] + m5["ask_open"]) / 2).to_numpy()[e]
        classes = {h["ny_hour"]: h["class"] for h in guide["assets"][asset]["hours"]}
        ny_hour = t.tz_convert("America/New_York").hour
        near_event = np.array([((ev_times >= x - pd.Timedelta(minutes=30)) & (ev_times <= x + pd.Timedelta(hours=2))).any() for x in t])
        base = pd.DataFrame({
            "time": t, "day": t.tz_convert("America/New_York").date, "slot": (t - pd.Timedelta(hours=-data["brasilia_utc_offset_hours"])).strftime("%H:%M"),
            "ny_class": [classes.get(h, "fechado") for h in ny_hour], "near_event": near_event,
            "spread_r": (m5["ask_open"].to_numpy()[e] - m5["bid_open"].to_numpy()[e]) / stop,
            "r_long": sim["long"][0], "hit_long": sim["long"][1], "r_short": sim["short"][0], "hit_short": sim["short"][1],
            "sig_24h": np.sign(mid_now - past_mid(m5, e, 24)), "sig_1h": -np.sign(mid_now - past_mid(m5, e, 1)),
        })
        base["follows"] = ~base["ny_class"].isin(SKIP_CLASSES) & ~base["near_event"]
        frames = {"aleatorio": base.assign(r=(base.r_long + base.r_short) / 2, hit=(base.hit_long.astype(float) + base.hit_short) / 2)}
        for rule, col in (("acompanha_24h", "sig_24h"), ("contra_1h", "sig_1h")):
            f = base[base[col] != 0].copy()
            longs = f[col] > 0
            f["r"] = np.where(longs, f.r_long, f.r_short)
            f["hit"] = np.where(longs, f.hit_long, f.hit_short).astype(float)
            frames[rule] = f
        res = {"entries": int(len(base)), "skipped_by_oneb": {
            "hora_ruim": int((base.ny_class.isin(SKIP_CLASSES)).sum()), "evento": int((~base.ny_class.isin(SKIP_CLASSES) & base.near_event).sum())},
            "users": {}, "by_slot": {}, "direction_test": {}}
        for period, (lo, hi) in periods.items():
            for user in ("segue_oneb", "ignora_oneb"):
                for rule in RULES:
                    f = frames[rule]
                    f = f[(f.time >= lo) & (f.time < hi)]
                    if user == "segue_oneb":
                        f = f[f.follows]
                    res["users"].setdefault(period, {}).setdefault(user, {})[rule] = summarize(f, plan["start_balance_usd"], plan["risk_per_trade"])
            for rule in RULES:
                f = frames[rule]
                f = f[(f.time >= lo) & (f.time < hi) & f.follows]
                res["by_slot"].setdefault(period, {})[rule] = [
                    {"slot": s, "trades": int(len(g)), "p_target": round(float(g.hit.mean()), 4), "mean_r": round(float(g.r.mean()), 4)}
                    for s, g in sorted(f.groupby("slot"), key=lambda x: x[0])]
        rnd = frames["aleatorio"].set_index("time")["r"]
        for rule in ("acompanha_24h", "contra_1h"):
            f = frames[rule][frames[rule].follows]
            diff = f["r"].to_numpy() - rnd.reindex(f["time"]).to_numpy()
            f = f.assign(diff=diff)
            disc = f[(f.time >= periods["discovery"][0]) & (f.time < periods["discovery"][1])]
            conf = f[(f.time >= periods["confirmation"][0]) & (f.time < periods["confirmation"][1])]
            lo_ci, hi_ci = bootstrap_ci(conf["diff"], conf["day"], level, 2000, 7)
            d_disc, d_conf, abs_conf = float(disc["diff"].mean()), float(conf["diff"].mean()), float(conf["r"].mean())
            passed = bool(d_conf > 0 and lo_ci > 0 and d_disc > 0 and abs_conf > 0)
            res["direction_test"][rule] = {"diff_discovery": round(d_disc, 4), "diff_confirmation": round(d_conf, 4),
                                           "ci": [round(lo_ci, 4), round(hi_ci, 4)], "ci_level": round(level, 4),
                                           "mean_r_confirmation": round(abs_conf, 4), "trades_confirmation": int(len(conf)), "passed": passed}
        out["assets"][asset] = res
        print(asset, json.dumps(res["direction_test"]), flush=True)
        print(asset, json.dumps(res["users"]["confirmation"]), flush=True)
    out["passed_rules"] = [f"{a}:{r}" for a, v in out["assets"].items() for r, d in v["direction_test"].items() if d["passed"]]
    path = ROOT / "app" / "research_results" / "replay_v1.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(path, "aprovadas:", out["passed_rules"])


if __name__ == "__main__":
    main()
