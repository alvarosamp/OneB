"""Executa o teste pré-registrado hours_v1: a hora de entrada muda o resultado do plano padrão?

    python scripts/run_hours.py

Relatório em D:/OneB/research/hours_v1/, resumo em app/research_results/hours_v1.json.
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

from app.research_paths import RESEARCH_ROOT  # noqa: E402
from app.setups import load_preregistered  # noqa: E402
from build_trade_plan_rates import load  # noqa: E402
from run_ctx import per_entry  # noqa: E402
from run_lab import benjamini_hochberg  # noqa: E402

RESAMPLES = 2000


def hour_diffs(df: pd.DataFrame, direction: str, resamples: int = RESAMPLES, seed: int = 7) -> dict[int, dict]:
    """Para cada hora: diferença (média da hora - média da direção) e distribuição bootstrap por dias."""
    g = df[df["direction"] == direction]
    days = pd.Index(sorted(g["day"].unique()))
    di = days.get_indexer(g["day"])
    r = g["r"].to_numpy()
    h = g["ny_hour"].to_numpy()
    tot_s = np.bincount(di, weights=r, minlength=len(days))
    tot_c = np.bincount(di, minlength=len(days)).astype(float)
    hour_s = {k: np.bincount(di[h == k], weights=r[h == k], minlength=len(days)) for k in range(24)}
    hour_c = {k: np.bincount(di[h == k], minlength=len(days)).astype(float) for k in range(24)}
    rng = np.random.default_rng(seed)
    boots = {k: np.empty(resamples) for k in range(24)}
    for i in range(resamples):
        pick = rng.integers(0, len(days), len(days))
        base = tot_s[pick].sum() / tot_c[pick].sum()
        for k in range(24):
            c = hour_c[k][pick].sum()
            boots[k][i] = hour_s[k][pick].sum() / c - base if c else np.nan
    out = {}
    base = r.mean()
    for k in range(24):
        m = h == k
        if m.sum() < 200:
            continue
        b = boots[k][np.isfinite(boots[k])]
        diff = float(r[m].mean() - base)
        p = float(min(1.0, 2 * min((b <= 0).mean(), (b >= 0).mean())))
        out[k] = {"n": int(m.sum()), "mean_r": round(float(r[m].mean()), 4), "diff_r": round(diff, 4), "p": p,
                  "boot": b}
    return out


def main() -> None:
    spec, sha = load_preregistered("hours_v1")
    disc, conf = spec["split"]["discovery"], spec["split"]["confirmation"]
    frames = {}
    cells = {}
    for asset in spec["data"]["assets"]:
        m5 = load(asset)
        frames[asset] = {"discovery": per_entry(m5, disc["from_inclusive"], disc["to_exclusive"]),
                         "confirmation": per_entry(m5, conf["from_inclusive"], conf["to_exclusive"])}
        for direction in ("long", "short"):
            for hour, v in hour_diffs(frames[asset]["discovery"], direction).items():
                cells[f"{asset}|{direction}|{hour}"] = v
    q = benjamini_hochberg({k: v["p"] for k, v in cells.items()})
    survivors = [k for k in cells if q[k] <= 0.10]
    print("células:", len(cells), "sobreviventes da descoberta:", survivors, flush=True)
    confirmed = []
    conf_rows = {}
    alpha = 0.05 / max(len(survivors), 1)
    cache = {}
    for key in survivors:
        asset, direction, hour = key.split("|")
        if (asset, direction) not in cache:
            cache[(asset, direction)] = hour_diffs(frames[asset]["confirmation"], direction, seed=11)
        c = cache[(asset, direction)].get(int(hour))
        if not c:
            continue
        lo, hi = np.quantile(c["boot"], [alpha / 2, 1 - alpha / 2])
        same_sign = np.sign(c["diff_r"]) == np.sign(cells[key]["diff_r"])
        ok = bool(same_sign and (lo > 0 or hi < 0) and c["mean_r"] > 0)
        conf_rows[key] = {"diff_r": c["diff_r"], "mean_r": c["mean_r"], "n": c["n"], "ci": [round(float(lo), 4), round(float(hi), 4)], "passed": ok}
        if ok:
            confirmed.append(key)
    table = {}
    for asset in spec["data"]["assets"]:
        for direction in ("long", "short"):
            for phase in ("discovery", "confirmation"):
                d = hour_diffs(frames[asset][phase], direction, resamples=200, seed=3)
                table.setdefault(asset, {}).setdefault(direction, {})[phase] = {
                    str(h): {"n": v["n"], "mean_r": v["mean_r"], "diff_r": v["diff_r"]} for h, v in d.items()}
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "test": "hours_v1", "spec_sha256": sha,
              "cells": len(cells), "discovery_survivors": survivors,
              "discovery": {k: {x: (round(y, 4) if isinstance(y, float) else y) for x, y in v.items() if x != "boot"} | {"q": round(q[k], 4)}
                            for k, v in cells.items()},
              "confirmation": conf_rows, "approved": confirmed,
              "status": "PASSED" if confirmed else "NOT_PASSED", "by_hour": table}
    out = RESEARCH_ROOT / "hours_v1"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"hours_v1_{datetime.now(timezone.utc):%Y%m%d}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (ROOT / "app" / "research_results" / "hours_v1.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "approved": confirmed, "confirmation": conf_rows}, indent=1))
    best = sorted(cells.items(), key=lambda kv: kv[1]["p"])[:8]
    print("menores p na descoberta:", [(k, v["diff_r"], round(v["p"], 4), round(q[k], 3)) for k, v in best])


if __name__ == "__main__":
    main()
