"""Laboratório lab_v1: descoberta e confirmação separadas, com Benjamini-Hochberg.

    python scripts/run_lab.py discovery            # todos os candidatos, só 2019-2022
    python scripts/run_lab.py confirmation         # SÓ sobreviventes, 2023-2026 (uma vez)

A fase de confirmação exige o arquivo de sobreviventes da descoberta com hash
conferido e recusa rodar duas vezes (resultado é definitivo).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.execution_sim import CostModel, replay_ready_signals  # noqa: E402
from app.forward_stats import COMPLETED, bootstrap_mean_ci  # noqa: E402
from app.lab.data import available_assets, load_m5  # noqa: E402
from app.lab.families import candidates  # noqa: E402
from app.research_paths import LAB_OUTPUT  # noqa: E402
from app.setups import load_preregistered  # noqa: E402

OUT = LAB_OUTPUT  # HD externo (app.research_paths)


def bootstrap_p_value(rs: list[float], resamples: int = 10_000, seed: int = 7) -> float | None:
    """p unilateral de H0: média <= 0."""
    if len(rs) < 2:
        return None
    arr = np.asarray(rs)
    means = arr[np.random.default_rng(seed).integers(0, len(arr), size=(resamples, len(arr)))].mean(axis=1)
    return float((means <= 0).mean())


def benjamini_hochberg(pvals: dict[str, float]) -> dict[str, float]:
    keys = [k for k, v in pvals.items() if v is not None]
    ordered = sorted(keys, key=lambda k: pvals[k])
    m = len(ordered)
    q = {}
    prev = 1.0
    for rank in range(m, 0, -1):
        k = ordered[rank - 1]
        prev = min(prev, pvals[k] * m / rank)
        q[k] = prev
    return q


def evaluate(asset: str, name: str, m5: pd.DataFrame, meta: dict, period: dict) -> dict:
    signals = candidates(asset)[name](m5)
    t0, t1 = pd.Timestamp(period["from_inclusive"]), pd.Timestamp(period["to_exclusive"])
    signals = [s for s in signals if t0 <= pd.Timestamp(s["at"]) < t1]
    costs = CostModel(point=1.0, slippage=meta["slippage_per_side"], commission_roundtrip=meta["commission_roundtrip"],
                      max_gap_minutes=120)
    trades, _ = replay_ready_signals(m5, signals, costs)
    rs = [t.r for t in trades if t.outcome in COMPLETED and t.r is not None]
    ci = bootstrap_mean_ci(rs)
    return {"asset": asset, "candidate": name, "signals": len(signals), "trades": len(rs),
            "expectancy_r": round(float(np.mean(rs)), 4) if rs else None,
            "ci95": [round(ci[0], 4), round(ci[1], 4)] if ci else None,
            "win_rate": round(float(np.mean([r > 0 for r in rs])), 4) if rs else None,
            "p_value": bootstrap_p_value(rs), "rs": rs,
            "entry_times": [t.entry_at for t in trades if t.outcome in COMPLETED and t.r is not None]}


def discovery(spec: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # Ativos do pré-registro menos os excluídos por emenda; nunca "o que houver no disco".
    planned = [a for a in spec["assets"] if a not in spec.get("assets_excluded", {})]
    assets = [a for a in planned if a in available_assets()]
    missing = [a for a in planned if a not in assets]
    rows = []
    for asset in assets:
        m5, meta = load_m5(asset)
        for name in candidates(asset):
            row = evaluate(asset, name, m5, meta, spec["split"]["discovery"])
            row.pop("rs"), row.pop("entry_times")
            rows.append(row)
            print(f"{asset:7s} {name:22s} trades={row['trades']:5d} exp={row['expectancy_r']} p={row['p_value']}", flush=True)
    eligible = {f"{r['asset']}|{r['candidate']}": r["p_value"] for r in rows if r["trades"] >= spec["selection"]["min_trades_discovery"]}
    # Candidatos com poucos trades contam na correção como p=1 (não podem ser descartados para facilitar).
    pvals = {f"{r['asset']}|{r['candidate']}": (eligible.get(f"{r['asset']}|{r['candidate']}", 1.0) or 1.0) for r in rows}
    q = benjamini_hochberg(pvals)
    for r in rows:
        r["q_value"] = round(q[f"{r['asset']}|{r['candidate']}"], 4)
    survivors = [f"{r['asset']}|{r['candidate']}" for r in rows if r["q_value"] <= 0.10 and r["trades"] >= spec["selection"]["min_trades_discovery"]]
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "phase": "discovery", "assets_run": assets,
              "assets_missing": missing, "assets_excluded": spec.get("assets_excluded", {}), "candidates_total": len(rows), "survivors": survivors, "rows": rows,
              "expected_false_discoveries_at_q10": round(0.10 * max(len(survivors), 1), 2)}
    path = OUT / "discovery.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (OUT / "discovery.sha256").write_text(digest, encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("assets_run", "assets_missing", "candidates_total", "survivors")}, indent=1))


def confirmation(spec: dict) -> None:
    path = OUT / "discovery.json"
    if not path.exists():
        raise SystemExit("Rode a descoberta antes.")
    if hashlib.sha256(path.read_bytes()).hexdigest() != (OUT / "discovery.sha256").read_text().strip():
        raise SystemExit("discovery.json foi alterado depois de gerado.")
    result_path = OUT / "confirmation.json"
    if result_path.exists():
        raise SystemExit("Confirmação já foi feita; o resultado é definitivo (pré-registro).")
    disc = json.loads(path.read_text(encoding="utf-8"))
    if disc["assets_missing"]:
        raise SystemExit(f"Descoberta incompleta (faltaram {disc['assets_missing']}); refaça a descoberta com todos os ativos.")
    rows = []
    cache = {}
    for key in disc["survivors"]:
        asset, name = key.split("|")
        if asset not in cache:
            cache[asset] = load_m5(asset)
        m5, meta = cache[asset]
        row = evaluate(asset, name, m5, meta, spec["split"]["confirmation"])
        recent = spec["split"]["recent_window"]
        rr = [r for r, t in zip(row["rs"], row["entry_times"])
              if pd.Timestamp(recent["from_inclusive"]) <= pd.Timestamp(t) < pd.Timestamp(recent["to_exclusive"])]
        row["recent_expectancy_r"] = round(float(np.mean(rr)), 4) if rr else None
        row["recent_trades"] = len(rr)
        row["passed"] = bool(row["ci95"] and row["ci95"][0] > 0 and rr and np.mean(rr) > 0)
        row.pop("rs"), row.pop("entry_times")
        rows.append(row)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "phase": "confirmation",
              "discovery_sha256": (OUT / "discovery.sha256").read_text().strip(), "rows": rows,
              "confirmed": [f"{r['asset']}|{r['candidate']}" for r in rows if r["passed"]]}
    result_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["discovery", "confirmation"])
    args = parser.parse_args()
    spec, _ = load_preregistered("lab_v1")
    discovery(spec) if args.phase == "discovery" else confirmation(spec)


if __name__ == "__main__":
    main()
