"""Replay pré-registrado de um setup sobre barras do broker + baselines.

Confere o LOCK do pré-registro, roda a máquina de estados causal, executa os
sinais com custos (app.execution_sim), compara com baselines de mesma execução
e aplica a regra de decisão registrada. Nenhuma ordem é enviada.

    python scripts/run_setup_replay.py --setup gold_fakeout_open_v1 \
        --bars "D:/OneB/market-data/mt5/HonorPro/XAUUSD.s_M5_2021-01-01_2026-09-14.csv.gz"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.baselines import PlainBreakout, random_entry_distribution, ready_signals  # noqa: E402
from app.execution_sim import CostModel, replay_ready_signals  # noqa: E402
from app.forward_stats import sample_size_note, summarize, verdict  # noqa: E402
from app.setups import build_setup, load_preregistered  # noqa: E402
from app.setups.base import resample_bars  # noqa: E402


def load_m5(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["timestamp"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_localize(None)
    frame = frame.drop_duplicates("timestamp", keep="last").sort_values("timestamp").set_index("timestamp")
    bad = (frame["high"] < frame[["open", "close", "low"]].max(axis=1)) | (frame["low"] > frame[["open", "close", "high"]].min(axis=1))
    if bad.any():
        raise ValueError(f"OHLC inválido em {int(bad.sum())} linhas")
    return frame[["open", "high", "low", "close", "spread", "tick_volume"]]


def signal_features(m10_features: pd.DataFrame, signal: dict, timeframe: int) -> dict:
    """Features no instante do READY (só passado), para o Signal Quality da Fase 3."""
    # `at` é o fechamento da barra; a linha correspondente é indexada pela abertura.
    at = pd.Timestamp(signal["at"]) - pd.Timedelta(minutes=timeframe)
    row = m10_features.loc[at]
    atr = m10_features["atr14"].loc[at]
    side = 1 if signal["direction"] == "long" else -1
    return {
        "atr14": round(float(atr), 4),
        "dist_sma_atr": round(side * (float(row["close"]) - float(row["sma"])) / float(atr), 4) if atr else None,
        "stop_dist_atr": round(abs(float(row["close"]) - float(signal["stop"])) / float(atr), 4) if atr else None,
        "break_excess_atr": round(side * (float(row["close"]) - float(signal["level"])) / float(atr), 4) if atr else None,
        "spread_points": float(row["spread"]),
        "brt_hour": int(signal.get("brt_hour", -1)),
        "weekday": int(at.dayofweek),
        "direction_long": int(side == 1),
        "range_ratio": round(float(m10_features["range_ratio"].loc[at]), 4),
    }


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup", default="gold_fakeout_open_v1")
    parser.add_argument("--bars", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline-seeds", type=int)
    args = parser.parse_args()

    config, config_sha = load_preregistered(args.setup)
    m5 = load_m5(args.bars)
    m10 = resample_bars(m5, int(config["timeframe_minutes"]), closed_before=m5.index[-1] + pd.Timedelta(minutes=5))
    setup = build_setup(config)
    transitions = setup.run(m10)

    features = setup.features(m10)
    true_range = pd.concat([features["high"] - features["low"], (features["high"] - features["close"].shift()).abs(),
                            (features["low"] - features["close"].shift()).abs()], axis=1).max(axis=1)
    features["atr14"] = true_range.rolling(14, min_periods=14).mean()
    features["range_ratio"] = (features["high"] - features["low"]) / features["atr14"]

    ready = ready_signals(transitions)
    for signal in ready:
        signal["features"] = signal_features(features, signal, int(config["timeframe_minutes"]))
    costs = CostModel.from_config(config)
    trades, ignored = replay_ready_signals(m5, ready, costs)
    sessions = int(pd.Index((m5.index - pd.Timedelta(hours=float(config["server_utc_offset_hours"]) + 3)).date).nunique())
    summary = summarize([t.to_dict() for t in trades], sessions=sessions)

    plain = PlainBreakout(config)
    plain_trades, _ = replay_ready_signals(m5, ready_signals(plain.run(m10)), costs)
    plain_summary = summarize([t.to_dict() for t in plain_trades], sessions=sessions)
    seeds = args.baseline_seeds or next(b["seeds"] for b in config["baselines"] if b["name"] == "random_entry")
    random_dist = random_entry_distribution(m5, trades, config, costs, seeds=seeds)
    strategy_pct = None
    if summary["expectancy_r"] is not None and random_dist.get("expectancies"):
        strategy_pct = round(sum(v <= summary["expectancy_r"] for v in random_dist["expectancies"]) / len(random_dist["expectancies"]) * 100, 1)
    decision = verdict(summary, config["decision_rule"], baseline_p95=random_dist.get("p95"))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "setup": args.setup,
        "setup_version": setup.version,
        "preregistration_sha256": config_sha,
        "git_commit": _git_commit(),
        "data": {
            "path": str(args.bars), "sha256": hashlib.sha256(args.bars.read_bytes()).hexdigest(),
            "m5_rows": len(m5), "m10_rows": len(m10), "first": m5.index[0].isoformat(), "last": m5.index[-1].isoformat(),
            "sessions": sessions, "clock": config["server_utc_offset_status"],
        },
        "transitions_by_state": dict(Counter(t.to_state.value for t in transitions)),
        "signals_ready": len(ready),
        "signals_ignored": dict(Counter(i["reason"] for i in ignored)),
        "summary": summary,
        "verdict": decision,
        "sample_size": sample_size_note(summary),
        "baselines": {
            "random_entry": {k: v for k, v in random_dist.items() if k != "expectancies"},
            "strategy_percentile_vs_random": strategy_pct,
            "plain_breakout": {k: plain_summary[k] for k in ("completed_trades", "expectancy_r", "expectancy_ci95", "win_rate", "profit_factor")},
        },
        "trades": [t.to_dict() for t in trades],
        "transitions": [t.to_dict() for t in transitions],
        "warning": "Replay sobre barras (não ticks); relógio do servidor assumido; custos hipotéticos. "
                   "Classificação permanece RESEARCH/SHADOW até a regra pré-registrada ser satisfeita.",
    }
    output = args.output or ROOT / "output" / "setup_research" / f"{args.setup}_{datetime.now(timezone.utc):%Y%m%d}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    brief = {k: report[k] for k in ("setup", "data", "transitions_by_state", "signals_ready", "signals_ignored", "verdict", "baselines")}
    brief["summary"] = {k: v for k, v in summary.items() if not k.startswith("by_")}
    print(json.dumps(brief, ensure_ascii=False, indent=2, default=str))
    print(f"\nRelatório: {output}")


if __name__ == "__main__":
    main()
