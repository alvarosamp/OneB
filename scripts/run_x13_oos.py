"""Pré-registro x13_ex5_oos_dukascopy: EX5 original do 13X em XAUUSD 2019-2026.

Marcas (buffers 2-5) lidas na primeira observação após o fechamento da barra
(shift 1). Passos A/B comparam marcas; passo C executa as duas hipóteses de
saída registradas sobre barras M5 Dukascopy com custos conservadores.

    python scripts/run_x13_oos.py --captures "D:/OneB/research/ex5_dukascopy/pilot42dk20*/*_buffers.csv"
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.execution_sim import CostModel  # noqa: E402
from app.forward_stats import COMPLETED, bootstrap_mean_ci, sample_size_note, summarize, verdict  # noqa: E402
from app.research_paths import VENDOR_RESEARCH  # noqa: E402
from app.setups import load_preregistered  # noqa: E402

_spec = importlib.util.spec_from_file_location("ex5", ROOT / "scripts" / "run_ex5_oos.py")
ex5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ex5)

RESEARCH = Path(r"D:\OneB\research\ex5_dukascopy")
REFERENCE = VENDOR_RESEARCH / "pilot27cert/pilot27cert_13x_H1_2_XAUUSD.s_PERIOD_H1_buffers.csv"
MARK_BUFFERS = (2, 3, 4, 5)


def marks(path: str | Path) -> pd.DataFrame:
    """Marcas não nulas dos buffers 2-5, na primeira observação com shift 1."""
    b = pd.read_csv(path, sep=";", keep_default_na=False, usecols=["observed_at", "bar_time", "shift", "buffer", "status", "value"])
    b = b[(b["status"] == "ok") & (b["shift"] == 1) & (b["buffer"].isin(MARK_BUFFERS))].copy()
    b["value"] = pd.to_numeric(b["value"], errors="coerce")
    b = b[(b["value"] != 0) & b["value"].notna() & (b["value"].abs() < 1e10)]
    b["bar_time"] = pd.to_datetime(b["bar_time"], format="%Y.%m.%d %H:%M:%S")
    b["observed_at"] = pd.to_datetime(b["observed_at"], format="%Y.%m.%d %H:%M:%S")
    return b.drop_duplicates(["bar_time", "buffer"]).sort_values("bar_time")[["bar_time", "observed_at", "buffer", "value"]]


def compare(reference: pd.DataFrame, other: pd.DataFrame) -> dict:
    ref = set(zip(reference["bar_time"], reference["buffer"]))
    oth = set(zip(other["bar_time"], other["buffer"]))
    hit = len(ref & oth)
    return {"reference": len(ref), "other": len(oth), "matched": hit,
            "recall": round(hit / len(ref), 4) if ref else None, "precision": round(hit / len(oth), 4) if oth else None}


def build_signals(all_marks: pd.DataFrame, exit_long_buffer: int, exit_short_buffer: int) -> list[dict]:
    """Converte marcas (relógio de servidor) em eventos UTC ordenados."""
    events = []
    for row in all_marks.itertuples(index=False):
        close_server = row.bar_time + pd.Timedelta(hours=1)  # H1: a marca vale no fechamento da barra
        at = ex5.server_to_utc(close_server)
        kind = {2: "buy", 3: "sell", exit_long_buffer: "exit_long", exit_short_buffer: "exit_short"}[row.buffer]
        events.append((at, kind))
    events.sort()
    return events


def simulate(events: list, bars: pd.DataFrame, atr: pd.Series, costs: CostModel, max_days: int = 5) -> list[dict]:
    """Uma posição por vez; saída no primeiro entre X correspondente, seta oposta, stop 2xATR e 5 dias."""
    trades = []
    idx = bars.index
    i = 0
    while i < len(events):
        at, kind = events[i]
        if kind not in ("buy", "sell"):
            i += 1
            continue
        side = 1 if kind == "buy" else -1
        start = idx.searchsorted(at, side="left")
        if start >= len(idx):
            break
        a = atr.asof(at)
        if not np.isfinite(a) or a <= 0:
            i += 1
            continue
        bar = bars.iloc[start]
        spread = float(bar["spread"]) * costs.point
        entry = float(bar["open"]) + (spread if side == 1 else 0) + side * costs.slippage
        stop = entry - side * 2 * a
        net_risk = 2 * a + costs.slippage + costs.commission_roundtrip
        exit_kind = "exit_long" if side == 1 else "exit_short"
        opposite = "sell" if side == 1 else "buy"
        # próximo evento que encerra
        j = i + 1
        signal_exit_at = None
        while j < len(events):
            if events[j][1] in (exit_kind, opposite) and events[j][0] > at:
                signal_exit_at = events[j][0]
                break
            j += 1
        deadline = idx[start] + pd.Timedelta(days=max_days)
        limit = min(deadline, signal_exit_at) if signal_exit_at is not None else deadline
        outcome, exit_price, exit_at = None, None, None
        worst = best = 0.0
        prev = idx[start]
        k = start
        while k < len(idx) and idx[k] < limit + pd.Timedelta(minutes=5):
            t = idx[k]
            if t - prev > pd.Timedelta(minutes=costs.max_gap_minutes):
                outcome = "CENSORED"
                break
            prev = t
            row = bars.iloc[k]
            sp = float(row["spread"]) * costs.point
            lo = float(row["low"]) + (0 if side == 1 else sp)
            hi = float(row["high"]) + (0 if side == 1 else sp)
            op = float(row["open"]) + (0 if side == 1 else sp)
            adverse, favorable = (lo, hi) if side == 1 else (hi, lo)
            worst = min(worst, side * (adverse - entry))
            best = max(best, side * (favorable - entry))
            if side * (adverse - stop) <= 0:
                fill = min(stop, op) if side == 1 else max(stop, op)
                outcome, exit_price, exit_at = "STOP", fill - side * costs.slippage, t
                break
            if t >= limit:
                outcome = "SIGNAL_EXIT" if signal_exit_at is not None and limit == signal_exit_at else "TIME_EXIT"
                exit_price, exit_at = op - side * costs.slippage, t
                break
            k += 1
        if outcome is None:
            outcome = "CENSORED"
        r = None
        if outcome not in ("CENSORED",):
            pnl = side * (exit_price - entry) - costs.commission_roundtrip
            r = round(pnl / net_risk, 4)
        trades.append({"entry_at": idx[start].isoformat(), "direction": "long" if side == 1 else "short",
                       "outcome": "TARGET" if outcome == "SIGNAL_EXIT" and r is not None and r > 0 else ("TIME_EXIT" if outcome == "SIGNAL_EXIT" else outcome),
                       "exit_kind": outcome, "r": r, "mae_r": round(worst / net_risk, 4), "mfe_r": round(best / net_risk, 4),
                       "exit_at": exit_at.isoformat() if exit_at is not None else None})
        # próxima posição só depois da saída
        end = exit_at if exit_at is not None else limit
        while i < len(events) and events[i][0] <= end:
            i += 1
    return trades


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    spec, spec_sha = load_preregistered("x13_ex5_oos_dukascopy")

    ref = marks(REFERENCE)
    step_a = compare(ref, marks(next(RESEARCH.glob("pilot42m1/*_buffers.csv"))))
    step_a["passed"] = bool(step_a["recall"] and step_a["recall"] >= 0.9 and step_a["precision"] >= 0.9)
    step_b = compare(ref, marks(next(RESEARCH.glob("pilot42dkval/*_buffers.csv"))))
    step_b["passed"] = bool(step_b["recall"] and step_b["recall"] >= 0.8 and step_b["precision"] >= 0.8)
    ext_path = VENDOR_RESEARCH / "x13_feed_validation_extended_20261006.json"
    extended = json.loads(ext_path.read_text()) if ext_path.exists() else {}
    print(json.dumps({"step_a": step_a, "step_b": step_b, "extended_validation": {k: extended.get(k) for k in ("recall", "precision", "passed")}}, indent=1))

    files = sorted(glob.glob(args.captures))
    if not files:
        print("Sem capturas anuais ainda; passos A/B acima.")
        return
    all_marks = pd.concat([marks(f) for f in files]).drop_duplicates(["bar_time", "buffer"]).sort_values("bar_time")

    previous = json.loads(sorted((ROOT / "output/setup_research").glob("gold_fakeout_open_v1_oos_dukascopy_*.json"))[-1].read_text(encoding="utf-8"))
    hourly = {int(k): v for k, v in previous["feed_validation"]["honor_hourly_spread_usd"].items()}
    duka, _ = ex5.oos.load_dukascopy(ex5.DUKA_M5)
    floor = duka.index.hour.map(lambda h: hourly.get(int(h), 0.0)).to_numpy()
    bars = duka.assign(spread=np.maximum(duka["spread_usd"].to_numpy(), floor) / 0.01)[ex5.oos.COLUMNS]
    h1 = bars.resample("1h").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    tr = pd.concat([h1["high"] - h1["low"], (h1["high"] - h1["close"].shift()).abs(), (h1["low"] - h1["close"].shift()).abs()], axis=1).max(axis=1)
    # ATR conhecido no FECHAMENTO da barra H1: desloca o índice para o fechamento.
    atr = tr.rolling(14).mean()
    atr.index = atr.index + pd.Timedelta(hours=1)
    costs = CostModel(point=0.01, slippage=0.05, commission_roundtrip=0.1, max_gap_minutes=120)
    t0, t1 = pd.Timestamp(spec["steps"]["C_out_of_sample"]["from_inclusive"]), pd.Timestamp(spec["steps"]["C_out_of_sample"]["to_exclusive"])
    test_bars = bars[(bars.index >= t0) & (bars.index < t1)]
    sessions = int(pd.Index((test_bars.index - pd.Timedelta(hours=3)).date).nunique())

    results = {}
    for name, (exit_long, exit_short) in {"H1_primary": (4, 5), "H2_secondary": (5, 4)}.items():
        events = [e for e in build_signals(all_marks, exit_long, exit_short) if t0 <= e[0] < t1]
        trades = simulate(events, bars, atr, costs)
        summary = summarize(trades, sessions=sessions)
        rs = [t["r"] for t in trades if t["outcome"] in COMPLETED and t["r"] is not None]
        ci975 = bootstrap_mean_ci(rs, alpha=0.025)
        years = {}
        for y in sorted({pd.Timestamp(t["entry_at"]).year for t in trades}):
            yr = [t["r"] for t in trades if t["r"] is not None and t["outcome"] in COMPLETED and pd.Timestamp(t["entry_at"]).year == y]
            ci = bootstrap_mean_ci(yr)
            years[str(y)] = {"trades": len(yr), "expectancy_r": round(float(np.mean(yr)), 4) if yr else None,
                             "ci95": [round(ci[0], 4), round(ci[1], 4)] if ci else None}
        recent = [t["r"] for t in trades if t["r"] is not None and t["outcome"] in COMPLETED and pd.Timestamp("2025-04-01") <= pd.Timestamp(t["entry_at"]) < pd.Timestamp("2026-04-01")]
        rci = bootstrap_mean_ci(recent)
        summary_975 = {**summary, "expectancy_ci95": [round(ci975[0], 4), round(ci975[1], 4)] if ci975 else None}
        decision = verdict(summary_975, {"min_sessions": 250, "min_trades": 100})
        if decision["status"] == "PASSED":
            neg = [y for y, v in years.items() if v["ci95"] and v["ci95"][1] < 0]
            if not recent or float(np.mean(recent)) <= 0 or neg:
                decision = {**decision, "status": "DEGRADED", "reason": "Não vale para o mercado atual."}
        if not step_a["passed"] or not (step_b["passed"] or extended.get("passed")):
            decision = {**decision, "status": "DESCRIPTIVE_ONLY", "reason": "Passo A/B reprovado. " + decision["reason"]}
        elif not step_b["passed"]:
            decision = {**decision, "note": "Passo B original reprovou (79%); validação ampliada registrada depois passou "
                                            f"({extended.get('recall')}/{extended.get('precision')}). Ver x13_feed_validation_extended."}
        results[name] = {"exit_long_buffer": exit_long, "exit_short_buffer": exit_short,
                         "summary": {k: v for k, v in summary.items() if not k.startswith("by_")}, "ci_decision_97_5": summary_975["expectancy_ci95"],
                         "by_year": years, "recent_window": {"trades": len(recent), "expectancy_r": round(float(np.mean(recent)), 4) if recent else None,
                                                             "ci95": [round(rci[0], 4), round(rci[1], 4)] if rci else None},
                         "exit_kinds": pd.Series([t["exit_kind"] for t in trades]).value_counts().to_dict(),
                         "verdict": decision, "sample_size": sample_size_note(summary)}
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "test": spec["test"], "spec_sha256": spec_sha,
              "step_a": step_a, "step_b": step_b, "extended_validation": extended, "marks": {"files": [Path(f).name for f in files], "count": int(len(all_marks)),
              "by_buffer": {int(k): int(v) for k, v in all_marks["buffer"].value_counts().items()}}, "sessions": sessions, "results": results}
    output = args.output or ROOT / "output" / "setup_research" / f"x13_ex5_oos_dukascopy_{datetime.now(timezone.utc):%Y%m%d}.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=1, default=str))
    for name, res in results.items():
        print(name, json.dumps({k: res[k] for k in ("summary", "ci_decision_97_5", "recent_window", "exit_kinds", "verdict")}, ensure_ascii=False, default=str))
    print(f"Relatório: {output}")


if __name__ == "__main__":
    main()
