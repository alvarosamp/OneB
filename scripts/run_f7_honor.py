"""Teste pré-registrado f7_honor_v1: momentum intradiário no Nasdaq com o custo da HonorPro.

    python scripts/run_f7_honor.py

Roda UMA vez (recusa se o resultado já existe). Relatório em D:/OneB/research/f7_honor_v1/,
resumo versionado em app/research_results/f7_honor_v1.json.
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

from app.lab.data import load_m5  # noqa: E402
from app.research_paths import RESEARCH_ROOT  # noqa: E402
from app.setups import load_preregistered  # noqa: E402
from run_lab import bootstrap_p_value, evaluate  # noqa: E402

OUT = RESEARCH_ROOT / "f7_honor_v1"
CANDIDATE = "F7_mom_open_to_1500"


def run(m5: pd.DataFrame, meta: dict, costs: dict, spec: dict) -> dict:
    priced = m5.assign(spread=float(costs["spread_points"]))
    cost_meta = {**meta, "slippage_per_side": float(costs["slippage_points_per_side"]),
                 "commission_roundtrip": float(costs.get("commission", 0.0))}
    row = evaluate("NAS100", CANDIDATE, priced, cost_meta, spec["period"])
    lo, hi = pd.Timestamp(spec["recent_window"]["from_inclusive"]), pd.Timestamp(spec["recent_window"]["to_exclusive"])
    recent = [r for r, t in zip(row["rs"], row["entry_times"]) if lo <= pd.Timestamp(t) < hi]
    by_year: dict[str, list[float]] = {}
    for r, t in zip(row["rs"], row["entry_times"]):
        by_year.setdefault(str(pd.Timestamp(t).year), []).append(r)
    return {"trades": row["trades"], "expectancy_r": row["expectancy_r"], "ci95": row["ci95"], "win_rate": row["win_rate"],
            "p_value": bootstrap_p_value(row["rs"]), "recent_trades": len(recent),
            "recent_expectancy_r": round(float(np.mean(recent)), 4) if recent else None,
            "by_year": {y: {"trades": len(v), "expectancy_r": round(float(np.mean(v)), 4)} for y, v in sorted(by_year.items())}}


def main() -> None:
    spec, sha = load_preregistered("f7_honor_v1")
    OUT.mkdir(parents=True, exist_ok=True)
    result_path = OUT / "result.json"
    if result_path.exists():
        raise SystemExit("f7_honor_v1 já foi executado; o resultado é definitivo (pré-registro).")
    m5, meta = load_m5("NAS100")
    primary = run(m5, meta, spec["costs_primary"], spec)
    stress = run(m5, meta, spec["costs_stress"], spec)
    passed = bool(primary["ci95"] and primary["ci95"][0] > 0 and (primary["recent_expectancy_r"] or 0) > 0)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "test": spec["test"], "spec_sha256": sha,
              "status": "PASSED" if passed else "FAILED", "primary": primary, "stress_double_cost": stress,
              "pass_criteria": spec["pass_criteria"], "assumption": spec["assumption"]}
    result_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (ROOT / "app" / "research_results" / "f7_honor_v1.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                                                        encoding="utf-8")
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
