"""Diagnóstico FORA do pré-registro: os 64 candidatos do lab_v1 sem nenhum custo (descoberta 2019-2022).

    python scripts/lab_gross_diagnostic.py

Só para entender a reprovação: se as regras são positivas sem custo, foi o spread que as matou;
se continuam negativas, não há vantagem nem antes do custo. Não muda nenhum veredito.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.lab.data import load_m5  # noqa: E402
from app.lab.families import candidates  # noqa: E402
from app.research_paths import LAB_OUTPUT  # noqa: E402
from app.setups import load_preregistered  # noqa: E402
from run_lab import evaluate  # noqa: E402


def main() -> None:
    spec, _ = load_preregistered("lab_v1")
    net = {f"{r['asset']}|{r['candidate']}": r for r in json.loads((LAB_OUTPUT / "discovery.json").read_text())["rows"]}
    rows = []
    for asset in [a for a in spec["assets"] if a not in spec.get("assets_excluded", {})]:
        m5, meta = load_m5(asset)
        m5 = m5.assign(spread=0.0)
        free = {**meta, "slippage_per_side": 0.0, "commission_roundtrip": 0.0}
        for name in candidates(asset):
            r = evaluate(asset, name, m5, free, spec["split"]["discovery"])
            key = f"{asset}|{name}"
            row = {"key": key, "trades": r["trades"], "gross_r": r["expectancy_r"], "gross_ci95": r["ci95"],
                   "net_r": net[key]["expectancy_r"]}
            rows.append(row)
            print(json.dumps(row), flush=True)
    gross = [r["gross_r"] for r in rows if r["gross_r"] is not None]
    out = {"note": __doc__.strip(), "rows": rows, "gross_positive": int(sum(g > 0 for g in gross)),
           "gross_ci_above_zero": [r["key"] for r in rows if r["gross_ci95"] and r["gross_ci95"][0] > 0],
           "median_gross_r": float(np.median(gross)), "median_cost_r": float(np.median(
               [r["gross_r"] - r["net_r"] for r in rows if r["gross_r"] is not None and r["net_r"] is not None]))}
    (LAB_OUTPUT / "gross_diagnostic.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("gross_positive", "gross_ci_above_zero", "median_gross_r", "median_cost_r")}))


if __name__ == "__main__":
    main()
