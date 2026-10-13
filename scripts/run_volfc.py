"""Executa o teste pré-registrado volfc_v1 (previsão da amplitude do próximo dia).

    python scripts/run_volfc.py

Coeficientes estimados só em 2019-2022; avaliação em 2023-2026. Relatório em
D:/OneB/research/volfc_v1/, resumo versionado (com coeficientes) em app/research_results/volfc_v1.json.
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

from app import calendar_study as cs  # noqa: E402
from app import volfc  # noqa: E402
from app.lab.data import DUKASCOPY_FILES  # noqa: E402
from app.research_paths import RESEARCH_ROOT  # noqa: E402
from app.setups import load_preregistered  # noqa: E402

TRAIN_END = pd.Timestamp("2023-01-01")
EVENT_KINDS = {"CPI", "NFP", "FOMC"}


def load_m5(asset: str) -> pd.DataFrame:
    raw = pd.read_csv(DUKASCOPY_FILES[asset], usecols=["timestamp", "bid_high", "bid_low", "bid_close"])
    raw.index = pd.to_datetime(raw["timestamp"], utc=True)
    return raw.rename(columns={"bid_high": "high", "bid_low": "low", "bid_close": "close"})[["high", "low", "close"]]


def main() -> None:
    spec, sha = load_preregistered("volfc_v1")
    ev = spec["evaluation"]["period"]
    lo, hi = pd.Timestamp(ev["from_inclusive"]), pd.Timestamp(ev["to_exclusive"])
    events = cs.load_events(ROOT / "configs" / "events" / "macro_events_2019_2026.json")
    # Pré-registro: só CPI, payroll (NFP) e FOMC. A 1ª execução usou também PIB e PCE (erro, corrigido e divulgado).
    event_days = {pd.Timestamp(t.tz_convert(cs.NEW_YORK).date()) for kind, t in events if kind in EVENT_KINDS}

    per_asset, diffs, app_model = {}, [], {}
    for asset in spec["data"]["assets"]:
        days = volfc.trading_days(load_m5(asset))
        f = volfc.features(np.log(days["range"])).dropna()
        # o "amanhã" é o próximo dia de negociação do próprio arquivo
        nxt = pd.Series(f.index[1:].tolist() + [pd.NaT], index=f.index)
        f["event_next"] = [float(d in event_days) if pd.notna(d) else 0.0 for d in nxt]
        train, test = f[f.index < TRAIN_END], f[(f.index >= lo) & (f.index < hi)]
        X = ["d", "w", "m"]
        coef = volfc.fit_ols(train[X].to_numpy(), train["target"].to_numpy())
        coef_cal = volfc.fit_ols(train[X + ["event_next"]].to_numpy(), train["target"].to_numpy())
        resid = train["target"].to_numpy() - volfc.predict(coef, train[X].to_numpy())
        resid_cal = train["target"].to_numpy() - volfc.predict(coef_cal, train[X + ["event_next"]].to_numpy())
        c10, c90 = float(np.quantile(resid_cal, 0.10)), float(np.quantile(resid_cal, 0.90))
        q10, q90 = float(np.quantile(resid, 0.10)), float(np.quantile(resid, 0.90))

        y = test["target"].to_numpy()
        p_har = volfc.predict(coef, test[X].to_numpy())
        p_cal = volfc.predict(coef_cal, test[X + ["event_next"]].to_numpy())
        p_atr = test["atr14"].to_numpy()
        e_atr, e_har, e_cal = (y - p_atr) ** 2, (y - p_har) ** 2, (y - p_cal) ** 2
        inside = (y >= p_har + q10) & (y <= p_har + q90)
        inside_cal = (y >= p_cal + c10) & (y <= p_cal + c90)
        app_model[asset] = {"coef": [round(float(c), 6) for c in coef_cal], "q10": round(c10, 6), "q90": round(c90, 6),
                            "coverage80_test": round(float(inside_cal.mean()), 4), "event_multiplier": round(float(np.exp(coef_cal[-1])), 3)}
        bias_atr = float(np.mean(y - p_atr))
        per_asset[asset] = {
            "train_days": len(train), "test_days": len(test),
            "coef": [round(float(c), 6) for c in coef], "coef_with_events": [round(float(c), 6) for c in coef_cal],
            "resid_q10": round(q10, 6), "resid_q90": round(q90, 6),
            "mse_baseline": round(float(e_atr.mean()), 5), "mse_har": round(float(e_har.mean()), 5),
            "mse_har_calendar": round(float(e_cal.mean()), 5),
            "reduction_vs_baseline": round(float(1 - e_har.mean() / e_atr.mean()), 4),
            "reduction_calendar_vs_har": round(float(1 - e_cal.mean() / e_har.mean()), 4),
            "r2_har": round(float(1 - e_har.sum() / ((y - y.mean()) ** 2).sum()), 4),
            "baseline_bias_log": round(bias_atr, 4),
            "coverage80": round(float(inside.mean()), 4),
            "event_day_mean_ratio_test": round(float(np.exp(y[test["event_next"].to_numpy() == 1]).mean() / np.exp(y[test["event_next"].to_numpy() == 0]).mean()), 3),
            "typical_range_test": round(float(np.exp(y).mean()), 6),
        }
        diffs.append(pd.Series(e_atr - e_har, index=test.index, name=asset))
        print(asset, json.dumps({k: per_asset[asset][k] for k in ("reduction_vs_baseline", "r2_har", "coverage80", "reduction_calendar_vs_har", "baseline_bias_log", "event_day_mean_ratio_test")}), flush=True)

    d = pd.concat(diffs, axis=1, sort=True).mean(axis=1, skipna=True).dropna().to_numpy()
    ci = volfc.block_bootstrap_mean_ci(d)
    reductions = [v["reduction_vs_baseline"] for v in per_asset.values()]
    primary_pass = all(r > 0 for r in reductions) and float(np.mean(reductions)) >= 0.05 and ci[0] > 0
    coverage_pass = all(0.75 <= v["coverage80"] <= 0.85 for v in per_asset.values())
    calendar_in_app = all(v["reduction_calendar_vs_har"] > 0 for v in per_asset.values())
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "test": "volfc_v1", "spec_sha256": sha,
        "status": "PASSED" if primary_pass and coverage_pass else ("PARTIAL" if primary_pass else "FAILED"),
        "primary": {"mean_reduction": round(float(np.mean(reductions)), 4), "mse_diff_ci95": [round(ci[0], 5), round(ci[1], 5)],
                    "passed": primary_pass},
        "interval80_passed": coverage_pass, "calendar_variable_in_app": calendar_in_app, "assets": per_asset,
        "event_kinds": sorted(EVENT_KINDS),
        "app_model": app_model if calendar_in_app else {a: {**v, "coef": per_asset[a]["coef"] + [0.0], "q10": per_asset[a]["resid_q10"],
                                                            "q90": per_asset[a]["resid_q90"]} for a, v in app_model.items()},
        "app_model_note": "Coeficientes [b0, dia, semana, mês, evento amanhã]. Faixa de 80% pelos quantis dos resíduos de 2019-2022; cobertura 2023-2026 medida (descritiva para a variante com evento).",
        "correction": "1ª execução (10/10/2026) marcou também PIB e PCE como evento, divergindo do pré-registro (só CPI, payroll e FOMC). Corrigido e reexecutado; o resultado primário (HAR sem eventos) não depende disso.",
    }
    out = RESEARCH_ROOT / "volfc_v1"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"volfc_v1_{datetime.now(timezone.utc):%Y%m%d}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (ROOT / "app" / "research_results" / "volfc_v1.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("status", "primary", "interval80_passed", "calendar_variable_in_app")}, indent=1))


if __name__ == "__main__":
    main()
