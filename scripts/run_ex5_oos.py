"""Passos B e C do pré-registro gold_fakeout_ex5_oos_dukascopy (EX5 original).

B: compara os sinais do EX5 no símbolo personalizado XAUUSD.dk com os sinais do
   EX5 na HonorPro (capturas Model=4 de maio/2026).
C: extrai as entradas do EX5 das capturas 2019-2026, executa sobre barras M5
   Dukascopy com custos conservadores e aplica a regra de decisão + recência.

    python scripts/run_ex5_oos.py --captures "D:/OneB/research/ex5_dukascopy/pilot41dk*/*_objects.csv" \
        --validation "D:/OneB/research/ex5_dukascopy/pilot41dkval*/*_objects.csv"
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backtest_original_gold_ticks import signals_from_objects  # noqa: E402

from app.execution_sim import CostModel, replay_ready_signals  # noqa: E402
from app.forward_stats import COMPLETED, bootstrap_mean_ci, sample_size_note, summarize, verdict  # noqa: E402
from app.research_paths import VENDOR_RESEARCH  # noqa: E402
from app.setups import load_preregistered  # noqa: E402

_spec = importlib.util.spec_from_file_location("oos", ROOT / "scripts" / "run_oos_dukascopy.py")
oos = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(oos)

NEW_YORK = ZoneInfo("America/New_York")
DUKA_M5 = Path(r"D:\OneB\market-data\dukascopy-xau-2019-2026\normalized\XAUUSD_M5_2019-03-01_2026-09-26.csv.gz")
REFERENCES = [
    VENDOR_RESEARCH / "pilot28week/pilot28week_gold_M10_0_XAUUSD.s_PERIOD_M10_objects.csv",
    VENDOR_RESEARCH / "pilot29verify/pilot29verify_gold_M10_0_XAUUSD.s_PERIOD_M10_objects.csv",
]


def server_to_utc(server: pd.Timestamp) -> pd.Timestamp:
    """Inverso da regra de relógio do pré-registro (UTC+3 no DST dos EUA, senão UTC+2)."""
    candidate = server - pd.Timedelta(hours=3)
    is_dst = bool(candidate.tz_localize("UTC").tz_convert(NEW_YORK).dst())
    return candidate if is_dst else server - pd.Timedelta(hours=2)


def match_signals(reference: list[dict], other: list[dict]) -> dict:
    used, matched = set(), 0
    for r in reference:
        for j, n in enumerate(other):
            if j in used:
                continue
            if n["side"] == r["side"] and abs(n["decision"] - r["decision"]) <= pd.Timedelta(minutes=10) \
                    and abs(n["stop"] - r["stop"]) <= 0.5 and abs(n["target"] - r["target"]) <= 0.5:
                used.add(j)
                matched += 1
                break
    return {"reference": len(reference), "other": len(other), "matched": matched,
            "recall": round(matched / len(reference), 4) if reference else None,
            "precision": round(matched / len(other), 4) if other else None}


def step_b(validation_files: list[str], spec: dict) -> dict:
    reference = [s for f in REFERENCES for s in signals_from_objects(f)]
    other = [s for f in validation_files for s in signals_from_objects(f)]
    result = match_signals(reference, other)
    crit = spec["steps"]["B_custom_symbol"]
    result["passed"] = bool(result["recall"] and result["precision"] and result["recall"] >= 0.8 and result["precision"] >= 0.8)
    result["criterion"] = crit["pass"]
    return result


def load_signals(files: list[str]) -> tuple[list[dict], dict]:
    seen, out, per_file = set(), [], {}
    for f in sorted(files):
        signals = signals_from_objects(f)
        per_file[Path(f).name] = len(signals)
        for s in signals:
            if s["name"] in seen:
                continue
            seen.add(s["name"])
            utc = server_to_utc(pd.Timestamp(s["decision"]))
            out.append({"opportunity_id": f"ex5:{s['name']}", "at": utc.isoformat(),
                        "direction": "long" if s["side"] == 1 else "short",
                        "stop": float(s["stop"]), "target": float(s["target"]), "target_r": None,
                        "max_hold_minutes": 240, "brt_hour": int((utc - pd.Timedelta(hours=3)).hour)})
    out.sort(key=lambda s: s["at"])
    return out, per_file


def random_baseline(bars: pd.DataFrame, trades: list, costs: CostModel, seeds: int = 200) -> dict:
    """Mesmas horas UTC dos sinais reais, mesma direção, mesmas distâncias de stop/alvo."""
    real = [t for t in trades if t.outcome in COMPLETED]
    if not real:
        return {"seeds": 0}
    hours = [pd.Timestamp(t.entry_at).hour for t in real]
    by_hour = {h: np.flatnonzero(bars.index.hour == h) for h in set(hours)}
    geometry = [(t.direction, abs(t.entry - t.stop), abs(t.target - t.entry)) for t in real]
    values = []
    for seed in range(seeds):
        rng = np.random.default_rng(seed)
        signals = []
        for k, hour in enumerate(hours):
            pool = by_hour[hour]
            pos = int(pool[rng.integers(len(pool))])
            if pos + 1 >= len(bars):
                continue
            direction, stop_d, target_d = geometry[rng.integers(len(geometry))]
            side = 1 if direction == "long" else -1
            nxt = bars.iloc[pos + 1]
            est = float(nxt["open"]) + (float(nxt["spread"]) * costs.point if side == 1 else 0)
            signals.append({"opportunity_id": f"rand:{seed}:{k}", "at": (bars.index[pos] + pd.Timedelta(minutes=5)).isoformat(),
                            "direction": direction, "stop": est - side * stop_d, "target": est + side * target_d,
                            "target_r": None, "max_hold_minutes": 240})
        signals.sort(key=lambda s: s["at"])
        sim, _ = replay_ready_signals(bars, signals, costs)
        rs = [t.r for t in sim if t.outcome in COMPLETED]
        if rs:
            values.append(float(np.mean(rs)))
    arr = np.asarray(values)
    return {"seeds": len(values), "p05": round(float(np.quantile(arr, 0.05)), 4), "p50": round(float(np.quantile(arr, 0.5)), 4),
            "p95": round(float(np.quantile(arr, 0.95)), 4), "expectancies": values}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", required=True, help="glob dos *_objects.csv anuais (passo C)")
    parser.add_argument("--validation", required=True, help="glob dos *_objects.csv de maio/2026 no XAUUSD.dk (passo B)")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    spec, spec_sha = load_preregistered("gold_fakeout_ex5_oos_dukascopy")
    b = step_b(sorted(glob.glob(args.validation)), spec)

    previous = json.loads(sorted((ROOT / "output/setup_research").glob("gold_fakeout_open_v1_oos_dukascopy_*.json"))[-1].read_text(encoding="utf-8"))
    hourly = {int(k): v for k, v in previous["feed_validation"]["honor_hourly_spread_usd"].items()}
    duka, _ = oos.load_dukascopy(DUKA_M5)
    floor = duka.index.hour.map(lambda h: hourly.get(int(h), 0.0)).to_numpy()
    bars = duka.assign(spread=np.maximum(duka["spread_usd"].to_numpy(), floor) / 0.01)[oos.COLUMNS]

    c = spec["steps"]["C_out_of_sample"]
    t0, t1 = pd.Timestamp(c["period"]["from_inclusive"]), pd.Timestamp(c["period"]["to_exclusive"])
    signals, per_file = load_signals(glob.glob(args.captures))
    in_test = [s for s in signals if t0 <= pd.Timestamp(s["at"]) < t1]
    costs = CostModel(point=0.01, slippage=0.05, commission_roundtrip=0.1, max_gap_minutes=60)
    trades, ignored = replay_ready_signals(bars, in_test, costs)
    dicts = [t.to_dict() for t in trades]
    test_bars = bars[(bars.index >= t0) & (bars.index < t1)]
    sessions = int(pd.Index((test_bars.index - pd.Timedelta(hours=3)).date).nunique())
    summary = summarize(dicts, sessions=sessions)
    rand = random_baseline(test_bars, trades, costs)
    pct = round(float(np.mean(np.asarray(rand.get("expectancies", [])) <= summary["expectancy_r"])) * 100, 1) \
        if rand.get("expectancies") and summary["expectancy_r"] is not None else None

    completed = [t for t in dicts if t["outcome"] in COMPLETED]
    by_year = oos.yearly(completed, test_bars)
    recent = [t["r"] for t in completed if pd.Timestamp("2025-04-01") <= pd.Timestamp(t["entry_at"]) < pd.Timestamp("2026-04-01")]
    rci = bootstrap_mean_ci(recent)
    recent_stats = {"trades": len(recent), "expectancy_r": round(float(np.mean(recent)), 4) if recent else None,
                    "ci95": [round(rci[0], 4), round(rci[1], 4)] if rci else None}

    decision = verdict(summary, {"min_sessions": 250, "min_trades": 100}, baseline_p95=rand.get("p95"))
    if not b["passed"]:
        decision = {**decision, "status": "DESCRIPTIVE_ONLY", "reason": "Passo B reprovado: XAUUSD.dk não reproduz o EX5 na HonorPro. " + decision["reason"]}
    elif decision["status"] == "PASSED":
        negative_years = [y for y, v in by_year.items() if v["ci95"] and v["ci95"][1] < 0]
        if not recent or recent_stats["expectancy_r"] <= 0 or negative_years:
            decision = {**decision, "status": "DEGRADED",
                        "reason": f"Média positiva, mas não vale para o mercado atual (recente {recent_stats['expectancy_r']}R; anos negativos {negative_years})."}

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "test": spec["test"], "spec_sha256": spec_sha,
        "step_a": json.loads((VENDOR_RESEARCH / "gold_ex5_stepA_model1_vs_model4_20261006.json").read_text()),
        "step_b": b,
        "data": {"captures": per_file, "signals_total": len(signals), "signals_in_test": len(in_test), "sessions": sessions,
                 "test_sessions": sessions, "clock": "VERIFIED" if b["passed"] else "UNVERIFIED",
                 "first": str(t0.date()), "last": str(t1.date())},
        "signals_ignored": dict(Counter(i["reason"] for i in ignored)),
        "summary": summary, "by_year": by_year, "recent_window": recent_stats,
        "baselines": {"random_entry": {k: v for k, v in rand.items() if k != "expectancies"}, "strategy_percentile_vs_random": pct,
                      "plain_breakout": {"completed_trades": None, "expectancy_r": None, "expectancy_ci95": None, "win_rate": None, "profit_factor": None}},
        "verdict": decision, "sample_size": sample_size_note(summary), "trades": dicts,
        "scope": spec["scope_of_conclusion"],
    }
    output = args.output or ROOT / "output" / "setup_research" / f"gold_fakeout_ex5_oos_dukascopy_{datetime.now(timezone.utc):%Y%m%d}.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    brief = {k: report[k] for k in ("step_b", "data", "signals_ignored", "by_year", "recent_window", "baselines", "verdict")}
    brief["summary"] = {k: v for k, v in summary.items() if not k.startswith("by_")}
    print(json.dumps(brief, ensure_ascii=False, indent=2, default=str))
    print(f"\nRelatório: {output}")


if __name__ == "__main__":
    main()
