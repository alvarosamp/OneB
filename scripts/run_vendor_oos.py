"""Teste fora da amostra genérico para EX5 que desenham entrada/SL/TP (100 Pips, Caixa de Londres).

    python scripts/run_vendor_oos.py pips100           # passos A, B e C (se houver capturas anuais)
    python scripts/run_vendor_oos.py london

Lê o pré-registro do LOCK, compara sinais (A: Model=1 vs ticks reais; B: Dukascopy
vs HonorPro) e executa as hipóteses de saída registradas com custos conservadores.
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.execution_sim import CostModel, replay_ready_signals  # noqa: E402
from app.forward_stats import COMPLETED, bootstrap_mean_ci, sample_size_note, summarize, verdict  # noqa: E402
from app.setups import load_preregistered  # noqa: E402

_spec = importlib.util.spec_from_file_location("ex5", ROOT / "scripts" / "run_ex5_oos.py")
ex5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ex5)

RESEARCH = Path(r"D:\OneB\research\ex5_dukascopy")


def _objects(path: str | Path) -> pd.DataFrame:
    o = pd.read_csv(path, sep=";", keep_default_na=False)
    if (o["text"] == "TRUNCATED").any():
        raise ValueError(f"Captura truncada: {path}")
    o["observed"] = pd.to_datetime(o["observed_at"], format="%Y.%m.%d %H:%M:%S")
    return o


def extract_pips100(path: str | Path) -> list[dict]:
    o = _objects(path)
    initial = o["observed"].iloc[0]
    out, seen = [], set()
    for observed, snap in o.groupby("observed", sort=True):
        objs = snap.set_index("name")
        for name in snap["name"]:
            m = re.fullmatch(r"100PIPS_LV_ENTRY_(\d+)", name)
            if not m or name in seen:
                continue
            seen.add(name)
            if observed == initial:
                continue
            sid = m.group(1)
            keys = {k: f"100PIPS_LV_{k}_{sid}" for k in ("SL", "TP1", "TP2")}
            if any(v not in objs.index for v in keys.values()):
                continue
            entry = float(objs.loc[name, "price0"])
            stop = float(objs.loc[keys["SL"], "price0"])
            out.append({"name": name, "decision": observed, "side": -1 if stop > entry else 1, "entry": entry, "stop": stop,
                        "tp1": float(objs.loc[keys["TP1"], "price0"]), "tp2": float(objs.loc[keys["TP2"], "price0"])})
    return out


def extract_london(path: str | Path) -> list[dict]:
    o = _objects(path)
    initial = o["observed"].iloc[0]
    out, seen = [], set()
    for observed, snap in o.groupby("observed", sort=True):
        objs = snap.set_index("name")
        for name in snap["name"]:
            m = re.fullmatch(r"(LB\d+_\d+)_Arrow", name)
            if not m:
                continue
            # O vendedor reaproveita nomes em rodízio (guarda só as últimas caixas):
            # o sinal é identificado pela data e preço da seta, não pelo nome.
            key = (objs.loc[name, "time0"], objs.loc[name, "price0"])
            if key in seen:
                continue
            seen.add(key)
            if observed == initial:
                continue
            p = m.group(1)
            needed = [f"{p}_SL", f"{p}_TP1", f"{p}_TP2", f"{p}_Qual"]
            if any(k not in objs.index for k in needed):
                continue
            entry = float(objs.loc[name, "price0"])
            stop = float(objs.loc[f"{p}_SL", "price0"])
            qual = str(objs.loc[f"{p}_Qual", "text"])
            out.append({"name": f"LB@{key[0]}", "decision": observed, "side": -1 if stop > entry else 1, "entry": entry,
                        "stop": stop, "tp1": float(objs.loc[f"{p}_TP1", "price0"]), "tp2": float(objs.loc[f"{p}_TP2", "price0"]),
                        "quality": "forte" if "forte" in qual.lower() else "fraco" if "fraco" in qual.lower() else qual})
    return out


FAMILIES = {
    "pips100": {"spec": "pips100_ex5_oos_dukascopy", "case": "100pips_H1", "extract": extract_pips100,
                "ref": "pilot44ref", "m1": "pilot45m1", "dkval": "pilot45dkval", "years": "pilot45dk20*"},
    "london": {"spec": "london_ex5_oos_dukascopy", "case": "london_H1", "extract": extract_london,
               "ref": "pilot44ref", "m1": "pilot46m1", "dkval": "pilot46dkval", "years": "pilot46dk20*"},
}


def match(reference: list[dict], other: list[dict]) -> dict:
    used, hit = set(), 0
    for r in reference:
        for j, n in enumerate(other):
            if j in used:
                continue
            if n["side"] == r["side"] and abs(n["decision"] - r["decision"]) <= pd.Timedelta(minutes=10) and \
                    all(abs(n[k] - r[k]) <= 0.5 for k in ("entry", "stop", "tp1", "tp2")):
                used.add(j)
                hit += 1
                break
    return {"reference": len(reference), "other": len(other), "matched": hit,
            "recall": round(hit / len(reference), 4) if reference else None,
            "precision": round(hit / len(other), 4) if other else None}


def _capture(batch: str, case: str) -> str | None:
    files = glob.glob(str(RESEARCH / batch / f"*{case.split('_')[0]}*objects.csv"))
    return files[0] if files else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("family", choices=sorted(FAMILIES))
    args = parser.parse_args()
    fam = FAMILIES[args.family]
    spec, spec_sha = load_preregistered(fam["spec"])
    extract = fam["extract"]

    ref = extract(_capture(fam["ref"], fam["case"]))
    result = {"test": spec["test"], "spec_sha256": spec_sha, "generated_at": datetime.now(timezone.utc).isoformat()}
    m1_path, dk_path = _capture(fam["m1"], fam["case"]), _capture(fam["dkval"], fam["case"])
    if m1_path:
        result["step_a"] = match(ref, extract(m1_path))
        result["step_a"]["passed"] = bool(result["step_a"]["recall"] and result["step_a"]["recall"] >= 0.9 and result["step_a"]["precision"] >= 0.9)
    if dk_path:
        result["step_b"] = match(ref, extract(dk_path))
        result["step_b"]["passed"] = bool(result["step_b"]["recall"] and result["step_b"]["recall"] >= 0.8 and result["step_b"]["precision"] >= 0.8)
    print(json.dumps({k: result.get(k) for k in ("step_a", "step_b")}, indent=1, default=str))

    yearly = sorted(glob.glob(str(RESEARCH / fam["years"] / "*objects.csv")))
    if not yearly or "step_a" not in result or "step_b" not in result:
        print("Passo C ainda não disponível (faltam capturas).")
        return
    seen, signals = set(), []
    for f in yearly:
        for s in extract(f):
            if s["name"] in seen:
                continue
            seen.add(s["name"])
            signals.append(s)

    previous = json.loads(sorted((ROOT / "output/setup_research").glob("gold_fakeout_open_v1_oos_dukascopy_*.json"))[-1].read_text(encoding="utf-8"))
    hourly = {int(k): v for k, v in previous["feed_validation"]["honor_hourly_spread_usd"].items()}
    duka, _ = ex5.oos.load_dukascopy(ex5.DUKA_M5)
    floor = duka.index.hour.map(lambda h: hourly.get(int(h), 0.0)).to_numpy()
    bars = duka.assign(spread=np.maximum(duka["spread_usd"].to_numpy(), floor) / 0.01)[ex5.oos.COLUMNS]
    c = spec["steps"]["C_out_of_sample"]
    t0, t1 = pd.Timestamp(c["from_inclusive"]), pd.Timestamp(c["to_exclusive"])
    test_bars = bars[(bars.index >= t0) & (bars.index < t1)]
    sessions = int(pd.Index((test_bars.index - pd.Timedelta(hours=3)).date).nunique())
    costs = CostModel(point=0.01, slippage=0.05, commission_roundtrip=0.1, max_gap_minutes=120)

    hypotheses = spec["hypotheses"]
    variants = {"H1_primary": "tp1", "H2_secondary": "tp2"}
    if args.family == "london" and "H3_quality_forte" in hypotheses:
        variants["H3_quality_forte"] = "tp1_forte"
    result["signals_total"] = len(signals)
    result["results"] = {}
    for hname, target_key in variants.items():
        chosen = [s for s in signals if target_key != "tp1_forte" or s.get("quality") == "forte"]
        tk = "tp1" if target_key == "tp1_forte" else target_key
        rows = []
        for s in chosen:
            utc = ex5.server_to_utc(pd.Timestamp(s["decision"]))
            if not (t0 <= utc < t1):
                continue
            rows.append({"opportunity_id": s["name"], "at": utc.isoformat(), "direction": "long" if s["side"] == 1 else "short",
                         "stop": s["stop"], "target": s[tk], "target_r": None, "max_hold_minutes": 7200})
        rows.sort(key=lambda r: r["at"])
        trades, ignored = replay_ready_signals(bars, rows, costs)
        dicts = [t.to_dict() for t in trades]
        summary = summarize(dicts, sessions=sessions)
        rs = [t["r"] for t in dicts if t["outcome"] in COMPLETED and t["r"] is not None]
        # Bonferroni: alpha bilateral 0,05 dividido pelo número de hipóteses registradas.
        ci975 = bootstrap_mean_ci(rs, alpha=0.05 / len(variants))
        years = {}
        for y in sorted({pd.Timestamp(t["entry_at"]).year for t in dicts}):
            yr = [t["r"] for t in dicts if t["r"] is not None and t["outcome"] in COMPLETED and pd.Timestamp(t["entry_at"]).year == y]
            ci = bootstrap_mean_ci(yr)
            years[str(y)] = {"trades": len(yr), "expectancy_r": round(float(np.mean(yr)), 4) if yr else None,
                             "ci95": [round(ci[0], 4), round(ci[1], 4)] if ci else None}
        recent = [t["r"] for t in dicts if t["r"] is not None and t["outcome"] in COMPLETED and pd.Timestamp("2025-04-01") <= pd.Timestamp(t["entry_at"]) < pd.Timestamp("2026-04-01")]
        decision = verdict({**summary, "expectancy_ci95": [round(ci975[0], 4), round(ci975[1], 4)] if ci975 else None},
                           {"min_sessions": 250, "min_trades": 100})
        if decision["status"] == "PASSED":
            neg = [y for y, v in years.items() if v["ci95"] and v["ci95"][1] < 0]
            if not recent or float(np.mean(recent)) <= 0 or neg:
                decision = {**decision, "status": "DEGRADED", "reason": "Não vale para o mercado atual."}
        if not (result["step_a"]["passed"] and result["step_b"]["passed"]):
            decision = {**decision, "status": "DESCRIPTIVE_ONLY", "reason": "Passo A/B reprovado. " + decision["reason"]}
        result["results"][hname] = {"signals_in_test": len(rows), "ignored": len(ignored),
                                    "summary": {k: v for k, v in summary.items() if not k.startswith("by_")},
                                    "ci_decision_bonferroni": [round(ci975[0], 4), round(ci975[1], 4)] if ci975 else None,
                                    "by_year": years, "recent": {"trades": len(recent), "expectancy_r": round(float(np.mean(recent)), 4) if recent else None},
                                    "verdict": decision, "sample_size": sample_size_note(summary)}
    out = ROOT / "output" / "setup_research" / f"{spec['test']}_{datetime.now(timezone.utc):%Y%m%d}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    for h, r in result["results"].items():
        s = r["summary"]
        print(h, json.dumps({"trades": s["completed_trades"], "exp_r": s["expectancy_r"], "ci_bonferroni": r["ci_decision_bonferroni"],
                             "win": s["win_rate"], "pf": s["profit_factor"], "recent": r["recent"], "verdict": r["verdict"]["status"]}, ensure_ascii=False))
    print("Relatório:", out)


if __name__ == "__main__":
    main()
