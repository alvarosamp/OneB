from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

DATA_DIR = Path("data")


def _read_json(name: str) -> dict[str, Any] | None:
    path = DATA_DIR / name
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _money(value: Any) -> str:
    try:
        return f"US$ {float(value):,.2f}"
    except (TypeError, ValueError):
        return "n/d"


def _pct(value: Any) -> str:
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "n/d"


def _event_summary() -> dict[str, Any]:
    path = DATA_DIR / "paper_simulator_events.jsonl"
    if not path.exists():
        return {"exists": False}
    counts: Counter[str] = Counter()
    last_events: list[dict[str, Any]] = []
    calibrations: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        counts[str(event.get("type", "unknown"))] += 1
        last_events.append(event)
        if event.get("type") == "calibration":
            calibrations.append(event)
    return {
        "exists": True,
        "counts": dict(counts),
        "last_events": last_events[-12:],
        "last_calibration": calibrations[-1] if calibrations else None,
    }


def _calibration_summary(name: str) -> dict[str, Any] | None:
    data = _read_json(name)
    if not data:
        return None
    best = data.get("best") or {}
    folds = best.get("folds") or []
    return {
        "file": name,
        "capital": data.get("capital"),
        "tested_configs": data.get("tested_configs"),
        "best_params": best.get("params"),
        "mean_rank": best.get("mean_rank"),
        "worst_fold_rank": best.get("worst_fold_rank"),
        "losing_folds": best.get("losing_folds"),
        "folds": [
            {
                "return_pct": fold.get("return_pct"),
                "win_rate_pct": fold.get("win_rate_pct"),
                "profit_factor": fold.get("profit_factor"),
                "max_drawdown_pct": fold.get("max_drawdown_pct"),
                "closed_trades": fold.get("closed_trades"),
            }
            for fold in folds
        ],
    }


def build_report() -> dict[str, Any]:
    state = _read_json("paper_simulator_state.json") or {}
    replay = _read_json("paper_simulator_deep_replay.json") or {}
    events = _event_summary()
    calibrations = [
        item
        for item in [
            _calibration_summary("decision_strategy_calibration.json"),
            _calibration_summary("short_strategy_calibration.json"),
        ]
        if item
    ]

    warnings = []
    if replay and state and replay.get("initial_capital") != state.get("initial_capital"):
        warnings.append(
            "O replay historico usa capital diferente do estado ao vivo. "
            "Isso nao invalida o replay, mas nao compare os dois como se fossem a mesma carteira."
        )
    if replay.get("win_rate_pct", 0) and float(replay.get("win_rate_pct", 0)) < 50:
        warnings.append("O ultimo replay AI_FIRST operou, mas teve acerto baixo; trate como validacao agressiva.")
    last_calibration = events.get("last_calibration") if events.get("exists") else None
    if last_calibration:
        calibration = last_calibration.get("calibration", {})
        if float(calibration.get("precision_pct", 0)) < 70:
            warnings.append("A calibracao em background ainda nao atingiu a meta de 70% de precisao.")
    return {
        "state": {
            "initial_capital": state.get("initial_capital"),
            "cash": state.get("cash"),
            "open_positions": len(state.get("positions", {})),
            "closed_trades": len(state.get("closed_trades", [])),
        },
        "deep_replay": {
            "initial_capital": replay.get("initial_capital"),
            "final_value": replay.get("final_value"),
            "return_pct": replay.get("return_pct"),
            "buys": replay.get("buys"),
            "sells": replay.get("sells"),
            "closed_trades": replay.get("closed_trades"),
            "win_rate_pct": replay.get("win_rate_pct"),
            "profit_factor": replay.get("profit_factor"),
            "max_drawdown_pct": replay.get("max_drawdown_pct"),
            "open_positions": len(replay.get("open_positions", {})),
            "last_calibration": replay.get("last_calibration"),
        },
        "events": events,
        "calibrations": calibrations,
        "warnings": warnings,
    }


def main() -> None:
    report = build_report()
    print("AUDITORIA DA SIMULACAO")
    print("======================")
    state = report["state"]
    print(f"Estado ao vivo: capital { _money(state['initial_capital']) }, caixa { _money(state['cash']) }, "
          f"posicoes abertas {state['open_positions']}, trades fechados {state['closed_trades']}")

    replay = report["deep_replay"]
    print(
        f"Replay historico: inicial { _money(replay['initial_capital']) }, final { _money(replay['final_value']) }, "
        f"retorno { _pct(replay['return_pct']) }, acerto { _pct(replay['win_rate_pct']) }, "
        f"profit factor {replay['profit_factor']}, drawdown { _pct(replay['max_drawdown_pct']) }"
    )
    if replay.get("last_calibration"):
        cal = replay["last_calibration"]
        print(
            f"Ultima calibracao do replay: precisao { _pct(cal.get('precision_pct')) }, "
            f"falsos positivos {cal.get('false_positive')}, retorno medio 5d { _pct(cal.get('avg_5d_return_pct')) }, "
            f"status {cal.get('status')}"
        )

    events = report["events"]
    if events.get("exists"):
        print(f"Eventos registrados: {events['counts']}")
        last_cal = events.get("last_calibration")
        if last_cal:
            cal = last_cal.get("calibration", {})
            print(
                f"Ultima calibracao em background: precisao { _pct(cal.get('precision_pct')) }, "
                f"sinais {cal.get('signals')}, falsos positivos {cal.get('false_positive')}, "
                f"retorno medio 5d { _pct(cal.get('avg_5d_return_pct')) }, status {cal.get('status')}"
            )

    for item in report["calibrations"]:
        print(f"Calibracao {item['file']}: configs {item['tested_configs']}, melhor params {item['best_params']}")

    if report["warnings"]:
        print("Alertas:")
        for warning in report["warnings"]:
            print(f"- {warning}")

    (DATA_DIR / "simulation_audit_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
