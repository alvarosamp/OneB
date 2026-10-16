"""Guia de horários 'mastigado': quando operar cada ativo, quando evitar e por quê.

    python scripts/build_hours_guide.py

Junta três medições (todas já geradas):
- app/research_results/hour_heatmap.json: movimento e custo do spread por hora (2 anos de M5);
- app/research_results/trade_plan_rates.json: chance do plano padrão (1,5 ATR, 2R) por hora de entrada;
- app/research_results/hours_v1.json: teste pré-registrado "alguma hora tem vantagem de direção?" (não aprovado).

Critérios de classificação (escolhas declaradas, não testes):
- fechado: sem negociação na hora;
- evitar: spread consome >= 5% do movimento típico da hora OU spread >= 2x o spread mediano do ativo (virada de dia);
- parado: movimento < 0,7x a hora típica (o stop vira ruído e o custo pesa mais);
- pico: movimento >= 1,8x (melhor para atingir alvo, mas o stop também é atingido mais rápido: reduza o lote);
- boa: o resto.
- janela principal: horas boas ou de pico com movimento >= 1,2x (o mercado anda o bastante para stop e alvo fazerem sentido).
Horas em Nova York; a tela converte para Brasília.
"""
from __future__ import annotations

import json
import statistics as st
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "app" / "research_results"
WEEKDAYS = ["segunda", "terça", "quarta", "quinta", "sexta"]


def classify(ratio: float | None, cost: float | None, spread: float | None, spread_median: float) -> tuple[str, str]:
    if ratio is None:
        return "fechado", "Sem negociação nesta hora."
    if cost is not None and cost >= 0.05:
        return "evitar", f"O spread consome {cost * 100:.0f}% do movimento típico da hora."
    if spread is not None and spread >= 2 * spread_median:
        return "evitar", "Pico de spread (virada do dia na corretora)."
    if ratio < 0.7:
        return "parado", f"Mercado parado ({ratio:.1f}x a hora típica): o custo pesa mais e o stop vira ruído."
    if ratio >= 1.8:
        return "pico", f"Hora mais agitada ({ratio:.1f}x a hora típica): alvo chega mais rápido, mas o stop também. Use lote menor."
    return "boa", f"Movimento normal ({ratio:.1f}x) e custo baixo."


def windows(hours: list[dict], classes: set[str]) -> list[list[int]]:
    """Faixas contíguas (hora de NY) cujas classes estão em `classes`."""
    out, cur = [], []
    for h in hours:
        if h["class"] in classes:
            cur.append(h["ny_hour"])
        elif cur:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [[w[0], w[-1] + 1] for w in out]


def main() -> None:
    heat = json.loads((RES / "hour_heatmap.json").read_text(encoding="utf-8"))
    rates = json.loads((RES / "trade_plan_rates.json").read_text(encoding="utf-8"))
    test = json.loads((RES / "hours_v1.json").read_text(encoding="utf-8"))
    guide = {"generated_at": datetime.now(timezone.utc).isoformat(), "timezone": "America/New_York",
             "criteria": __doc__.split("Critérios de classificação")[1].split("Horas em Nova York")[0].strip(),
             "direction_test": {"test": "hours_v1", "status": test["status"], "cells": test["cells"],
                                "summary": f"Nenhuma das {test['cells']} combinações de hora, direção e ativo teve vantagem que se repetisse "
                                           "(correção para múltiplos testes). A hora muda o tamanho do movimento e o custo, não a chance de acertar a direção."},
             "assets": {}}
    for asset, a in heat["assets"].items():
        by_hour: dict[int, list[dict]] = {}
        by_day: dict[int, list[float]] = {}
        for c in a["cells"]:
            by_hour.setdefault(c["hour"], []).append(c)
            by_day.setdefault(c["weekday"], []).append(c["range_bps"])
        spread_median = st.median(c["spread_bps"] for c in a["cells"])
        recent = [r for r in rates["assets"].get(asset, {}).get("recent", []) if r["stop_atr"] == 1.5 and r["target_r"] == 2.0]
        hours = []
        for h in range(24):
            cs = by_hour.get(h, [])
            ratio = st.median(c["ratio"] for c in cs) if cs else None
            cost = st.median(c["cost_share"] for c in cs) if cs else None
            spread = st.median(c["spread_bps"] for c in cs) if cs else None
            klass, reason = classify(ratio, cost, spread, spread_median)
            p = {r["direction"]: r["p_target"] for r in recent if r["ny_hour"] == h}
            hours.append({"ny_hour": h, "ratio": ratio, "cost_share": cost, "spread_bps": spread, "class": klass, "reason": reason,
                          "p2r_long": p.get("long"), "p2r_short": p.get("short")})
        p_all = [x for h in hours for x in (h["p2r_long"], h["p2r_short"]) if x is not None]
        day_ratio = {WEEKDAYS[d]: round(st.median(v) / a["typical_range_bps"], 2) for d, v in sorted(by_day.items()) if d < 5}
        guide["assets"][asset] = {
            "label": a["label"], "broker_symbol": a.get("broker_symbol"), "period": a["period"], "hours": hours,
            "windows": {"principal": windows([{**h, "class": "x" if h["class"] in ("boa", "pico") and (h["ratio"] or 0) >= 1.2 else h["class"]}
                                              for h in hours], {"x"}),
                        "operar": windows(hours, {"boa", "pico"}), "pico": windows(hours, {"pico"}),
                        "evitar": windows(hours, {"evitar"}), "parado": windows(hours, {"parado"})},
            "plan_p2r_range": [min(p_all), max(p_all)] if p_all else None,
            "weekday_ratio": day_ratio,
            "all_expensive": all(h["class"] in ("evitar", "fechado") for h in hours),
        }
        print(asset, guide["assets"][asset]["windows"], "p2r", guide["assets"][asset]["plan_p2r_range"], day_ratio)
    (RES / "hours_guide.json").write_text(json.dumps(guide, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
