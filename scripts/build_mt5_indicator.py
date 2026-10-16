"""Gera o indicador OneB para o MetaTrader 5 (mt5/OneB_Risco.mq5) a partir dos resultados da pesquisa.

    python scripts/build_mt5_indicator.py

Embute no indicador, sem precisar de internet:
- os coeficientes da previsão de amplitude aprovada (app/research_results/volfc_v1.json);
- a chance medida de cada alvo do plano com stop de 1,5 ATR (trade_plan_rates.json, 2023-2026);
- a classificação de cada hora de Nova York (hours_guide.json).
O indicador não envia ordens e não dá sinal de compra ou venda. Rode de novo quando a pesquisa for atualizada.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "app" / "research_results"
OUT = ROOT / "mt5" / "OneB_Risco.mq5"
ASSETS = ["NAS100", "SPX500", "XAUUSD", "EURUSD"]
CLASS_CODE = {"boa": 0, "pico": 1, "parado": 2, "evitar": 3, "fechado": 4}


def arr(values, fmt="{:.6f}") -> str:
    return "{" + ",".join(fmt.format(v) for v in values) + "}"


def main() -> None:
    vf = json.loads((RESULTS / "volfc_v1.json").read_text(encoding="utf-8"))
    if vf.get("status") != "PASSED":
        sys.exit("volfc_v1 não está aprovado: o indicador não deve mostrar a previsão.")
    rates = json.loads((RESULTS / "trade_plan_rates.json").read_text(encoding="utf-8"))
    guide = json.loads((RESULTS / "hours_guide.json").read_text(encoding="utf-8"))
    coef, q10, q90, probs, hours = [], [], [], [], []
    for key in ASSETS:
        m = vf["app_model"][key]
        coef.append(arr(m["coef"]))
        q10.append(f"{m['q10']:.6f}")
        q90.append(f"{m['q90']:.6f}")
        rows = {(r["direction"], r["target_r"]): r["p_target"] for r in rates["assets"][key]["recent"] if r["ny_hour"] is None and r["stop_atr"] == 1.5}
        probs.append(arr([rows[(d, t)] for d in ("long", "short") for t in (1.0, 2.0, 3.0)], "{:.4f}"))
        cls = {h["ny_hour"]: CLASS_CODE[h["class"]] for h in guide["assets"][key]["hours"]}
        hours.append(arr([cls.get(h, 4) for h in range(24)], "{}"))
    spath = RESULTS / "sessfc_v1.json"
    smodel = (json.loads(spath.read_text(encoding="utf-8")).get("app_model") or {}) if spath.exists() else {}
    son, scoef, sq10, sq90 = [], [], [], []
    for key in ASSETS:  # só ativo aprovado no sessfc_v1 mostra a previsão até o fechamento
        m = smodel.get(key)
        son.append("1" if m else "0")
        scoef.append(arr(m["coef"] if m else [0.0] * 6))
        sq10.append(f"{m['q10']:.6f}" if m else "0.0")
        sq90.append(f"{m['q90']:.6f}" if m else "0.0")
    data = (
        f"// Gerado por scripts/build_mt5_indicator.py em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. Não edite à mão.\n"
        f"double COEF[4][5] = {{{','.join(coef)}}};\n"
        f"double Q10[4] = {{{','.join(q10)}}};\n"
        f"double Q90[4] = {{{','.join(q90)}}};\n"
        f"// chance medida do alvo antes do stop (stop 1,5 ATR de 1 h, 2023-2026): compra TP1..TP3, venda TP1..TP3\n"
        f"double PTARGET[4][6] = {{{','.join(probs)}}};\n"
        f"// hora de Nova York: 0 boa, 1 pico, 2 parado, 3 evitar, 4 fechado\n"
        f"int HOURCLASS[4][24] = {{{','.join(hours)}}};\n"
        f"// das 10:30 de Brasília ao fechamento de NY (sessfc_v1): const, d, w, m, pre, evento\n"
        f"int SESS_ON[4] = {{{','.join(son)}}};\n"
        f"double SESS_COEF[4][6] = {{{','.join(scoef)}}};\n"
        f"double SESS_Q10[4] = {{{','.join(sq10)}}};\n"
        f"double SESS_Q90[4] = {{{','.join(sq90)}}};\n"
    )
    template = (ROOT / "mt5" / "OneB_Risco.template.mq5").read_text(encoding="utf-8")
    OUT.write_text(template.replace("//@@DATA@@", data), encoding="utf-8-sig")  # MetaEditor lê UTF-8 com BOM
    print(OUT)


if __name__ == "__main__":
    main()
