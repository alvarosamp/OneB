from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from app import decision_engine as de
from app import paper_simulator as sim
from app.research_registry import create_experiment, save_experiment
from scripts.backtest_short_strategy import replay as short_replay
from scripts.calibrate_decision_strategy import (
    EMBARGO_DAYS,
    WALK_FORWARD_FOLDS,
    WALK_FORWARD_WINDOW_DAYS,
    StrategyParams,
    _walk_forward_folds,
)
from scripts.calibrate_decision_strategy import (
    replay as long_replay,
)
from scripts.compare_recommendations import DEFAULT_SYMBOLS, _load_prepared, _symbols

OUTPUT_PATH = Path(os.getenv("AUTOMATION_READINESS_PATH", "data/automation_readiness_report.json"))
MIN_TRADES = int(os.getenv("AUTOMATION_READY_MIN_TRADES", "20"))
MIN_SHARPE = float(os.getenv("AUTOMATION_READY_MIN_SHARPE", "0.8"))
MIN_PROFIT_FACTOR = float(os.getenv("AUTOMATION_READY_MIN_PROFIT_FACTOR", "1.25"))
MAX_DRAWDOWN_PCT = float(os.getenv("AUTOMATION_READY_MAX_DRAWDOWN_PCT", "15"))
MIN_WIN_RATE_PCT = float(os.getenv("AUTOMATION_READY_MIN_WIN_RATE_PCT", "52"))
MIN_POSITIVE_FOLDS = int(os.getenv("AUTOMATION_READY_MIN_POSITIVE_FOLDS", "3"))


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def _params_from_thresholds(thresholds: dict, *, short: bool = False) -> StrategyParams:
    return StrategyParams(
        min_score=int(thresholds["min_setup_score"]),
        min_volume_ratio=float(thresholds["min_volume_ratio"]),
        max_volatility=float(thresholds["max_volatility"]),
        stop_atr=float(thresholds["stop_atr"]),
        target_atr=float(thresholds["target_atr"]),
        weak_score=int(thresholds["weak_score"]),
        max_positions=sim.MAX_OPEN_POSITIONS,
    )


def _compact(metrics: dict) -> dict:
    keys = [
        "return_pct",
        "closed_trades",
        "win_rate_pct",
        "profit_factor",
        "sharpe_ratio",
        "sortino_ratio",
        "max_drawdown_pct",
        "gross_profit",
        "gross_loss",
        "buys",
        "sells",
        "partial_sells",
    ]
    return {key: metrics.get(key) for key in keys if key in metrics}


def _passes(metrics: dict) -> tuple[bool, list[str]]:
    failures = []
    if metrics.get("closed_trades", 0) < MIN_TRADES:
        failures.append(f"trades<{MIN_TRADES}")
    if (metrics.get("win_rate_pct") or 0) < MIN_WIN_RATE_PCT:
        failures.append(f"win_rate<{MIN_WIN_RATE_PCT}")
    profit_factor = metrics.get("profit_factor") or 0
    if profit_factor == 999:
        profit_factor = MIN_PROFIT_FACTOR
    if profit_factor < MIN_PROFIT_FACTOR:
        failures.append(f"profit_factor<{MIN_PROFIT_FACTOR}")
    if (metrics.get("sharpe_ratio") or 0) < MIN_SHARPE:
        failures.append(f"sharpe<{MIN_SHARPE}")
    if abs(min(0, metrics.get("max_drawdown_pct") or 0)) > MAX_DRAWDOWN_PCT:
        failures.append(f"drawdown>{MAX_DRAWDOWN_PCT}")
    return not failures, failures


def _side_report(name: str, folds: list[tuple[int, int]], replay_fn, prepared: dict, benchmark: dict | None, capital: float, params: StrategyParams) -> dict:
    fold_rows = []
    positive_folds = 0
    pass_folds = 0
    for start, end in folds:
        metrics = replay_fn(prepared, benchmark, capital, start, end, params)
        passed, failures = _passes(metrics)
        positive_folds += 1 if metrics.get("return_pct", 0) > 0 else 0
        pass_folds += 1 if passed else 0
        fold_rows.append(
            {
                "start_index": start,
                "end_index": end,
                "passed": passed,
                "failures": failures,
                "metrics": _compact(metrics),
            }
        )

    aggregate = {
        "positive_folds": positive_folds,
        "passed_folds": pass_folds,
        "total_folds": len(folds),
        "all_folds_pass": pass_folds == len(folds),
        "enough_positive_folds": positive_folds >= min(MIN_POSITIVE_FOLDS, len(folds)),
    }
    ready = aggregate["all_folds_pass"] and aggregate["enough_positive_folds"]
    return {
        "side": name,
        "ready_for_automation": ready,
        "params": asdict(params),
        "aggregate": aggregate,
        "folds": fold_rows,
    }


def build_report() -> dict:
    capital = float(os.getenv("PAPER_SIM_INITIAL_CAPITAL", "10000"))
    symbols = _symbols() or DEFAULT_SYMBOLS
    prepared, benchmark, skipped = _load_prepared(symbols)
    if not prepared:
        raise SystemExit("Nenhum simbolo com historico suficiente.")

    max_len = min(len(data["history"]) for data in prepared.values())
    folds = _walk_forward_folds(max_len, WALK_FORWARD_FOLDS, WALK_FORWARD_WINDOW_DAYS, min_start=65, embargo_days=EMBARGO_DAYS)
    long_params = _params_from_thresholds(de.effective_thresholds())
    short_params = _params_from_thresholds(de.short_effective_thresholds(), short=True)

    long_report = _side_report("long", folds, long_replay, prepared, benchmark, capital, long_params)
    short_report = _side_report("short", folds, short_replay, prepared, benchmark, capital, short_params)
    ready = long_report["ready_for_automation"] or short_report["ready_for_automation"]
    verdict = "AUTOMATION_READY" if ready else "HUMAN_APPROVAL_REQUIRED"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "capital": capital,
        "symbols": sorted(prepared),
        "skipped": skipped,
        "folds": [{"start_index": start, "end_index": end} for start, end in folds],
        "criteria": {
            "min_trades": MIN_TRADES,
            "min_win_rate_pct": MIN_WIN_RATE_PCT,
            "min_profit_factor": MIN_PROFIT_FACTOR,
            "min_sharpe": MIN_SHARPE,
            "max_drawdown_pct": MAX_DRAWDOWN_PCT,
            "min_positive_folds": MIN_POSITIVE_FOLDS,
        },
        "long": long_report,
        "short": short_report,
        "recommendation": (
            "Pode avancar para automacao em paper/live-sim com limites rigidos."
            if ready
            else "Ainda manter humano aprovando; automatizar apenas coleta, pesquisa, alertas e paper trading."
        ),
    }


def main() -> None:
    report = build_report()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    record = create_experiment(
        name="automation_readiness",
        hypothesis="Current long/short decision rules are robust enough for autonomous execution.",
        status="ACCEPTED" if report["verdict"] == "AUTOMATION_READY" else "REJECTED",
        git_commit=_git_commit(),
        dataset_version=f"market_history_period={sim.MARKET_HISTORY_PERIOD}",
        feature_set=sim.FEATURE_NAMES,
        universe=report["symbols"],
        training_period="walk_forward_folds",
        validation_period="all_folds",
        model="decision_engine_rules_v1",
        transaction_costs={"cost_bps": sim.COST_BPS, "slippage_bps": sim.SLIPPAGE_BPS},
        metrics={
            "verdict": report["verdict"],
            "long_ready": report["long"]["ready_for_automation"],
            "short_ready": report["short"]["ready_for_automation"],
        },
        artifacts={"automation_readiness_report": str(OUTPUT_PATH)},
        notes=report["recommendation"],
    )
    experiment_path = save_experiment(record)
    summary = {
        "verdict": report["verdict"],
        "recommendation": report["recommendation"],
        "symbols": report["symbols"],
        "skipped": report["skipped"],
        "criteria": report["criteria"],
        "long": report["long"]["aggregate"],
        "short": report["short"]["aggregate"],
        "report_path": str(OUTPUT_PATH),
        "experiment_record": str(experiment_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
