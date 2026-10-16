"""Executa o teste pré-registrado sessfc_v1 (quanto o preço ainda anda das 10:30 de Brasília ao fechamento de NY).

    python scripts/run_sessfc.py

Coeficientes estimados só em 2019-2022; avaliação em 2023-2026. Resumo versionado (com os coeficientes
para o app) em app/research_results/sessfc_v1.json.
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
from app import sessfc  # noqa: E402
from app.setups import load_preregistered  # noqa: E402
from build_trade_plan_rates import load  # noqa: E402

TRAIN_END = pd.Timestamp("2023-01-01")
EVENT_KINDS = {"CPI", "NFP", "FOMC"}


def main() -> None:
    spec, sha = load_preregistered("sessfc_v1")
    ev = spec["evaluation"]["period"]
    lo, hi = pd.Timestamp(ev["from_inclusive"]), pd.Timestamp(ev["to_exclusive"])
    events = cs.load_events(ROOT / "configs" / "events" / "macro_events_2019_2026.json")
    event_days = {t.tz_convert(cs.NEW_YORK).date() for kind, t in events if kind in EVENT_KINDS}
    level = 1 - 0.05 / len(spec["data"]["assets"])
    out = {"test": "sessfc_v1", "sha256": sha, "generated_at": datetime.now(timezone.utc).isoformat(), "assets": {}, "app_model": {}}
    for asset in spec["data"]["assets"]:
        raw = load(asset)
        m5 = pd.DataFrame({"open": raw["bid_open"], "high": raw["bid_high"], "low": raw["bid_low"], "close": raw["bid_close"]})
        win = sessfc.windows(m5)
        f = sessfc.features(win, event_days).dropna()
        train, test = f[f.index < TRAIN_END], f[(f.index >= lo) & (f.index < hi)]
        coef = sessfc.fit_ols(train[sessfc.FEATURES].to_numpy(), train["target"].to_numpy())
        resid = train["target"].to_numpy() - sessfc.predict(coef, train[sessfc.FEATURES].to_numpy())
        q10, q90 = float(np.quantile(resid, 0.10)), float(np.quantile(resid, 0.90))
        pred = sessfc.predict(coef, test[sessfc.FEATURES].to_numpy())
        y, base = test["target"].to_numpy(), test["m"].to_numpy()
        err_m, err_b = (y - pred) ** 2, (y - base) ** 2
        reduction = 1 - err_m.mean() / err_b.mean()
        ci = sessfc.block_bootstrap_mean_ci(err_b - err_m, level)
        coverage = float(((y >= pred + q10) & (y <= pred + q90)).mean())
        passed_err = bool(reduction >= 0.05 and ci[0] > 0)
        passed_cov = bool(0.75 <= coverage <= 0.85)
        out["assets"][asset] = {
            "train_days": int(len(train)), "test_days": int(len(test)), "mse_model": float(err_m.mean()), "mse_baseline": float(err_b.mean()),
            "reduction_vs_baseline": float(reduction), "ci_diff": [ci[0], ci[1]], "ci_level": level, "coverage80": coverage,
            "passed_error": passed_err, "passed_coverage": passed_cov, "passed": passed_err and passed_cov,
            "coef": dict(zip(["const", *sessfc.FEATURES], map(float, coef))),
            "median_range_pct_test": float(np.exp(np.median(y)) * 100),
        }
        if passed_err and passed_cov:
            out["app_model"][asset] = {"coef": [float(c) for c in coef], "q10": q10, "q90": q90}
        print(asset, json.dumps(out["assets"][asset], ensure_ascii=False), flush=True)
    out["passed_assets"] = sorted(out["app_model"])
    path = ROOT / "app" / "research_results" / "sessfc_v1.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(path, "aprovados:", out["passed_assets"])


if __name__ == "__main__":
    main()
