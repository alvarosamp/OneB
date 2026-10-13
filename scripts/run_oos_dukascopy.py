"""Teste fora da amostra pré-registrado: gold_fakeout_open_v1 em Dukascopy (2019-2026).

Segue configs/preregistration/gold_fakeout_open_v1_oos_dukascopy.json (conferido
contra o LOCK). Etapas, todas fixadas antes do download:
1. Valida o feed Dukascopy contra as barras HonorPro no período de sobreposição
   (correlação de retornos, diferença de preço, recall de sinais). O fuso do
   servidor HonorPro é ESTIMADO pelos dados (melhor offset), não assumido.
2. Custo conservador: por barra, o maior spread entre Dukascopy e a mediana
   HonorPro da mesma hora UTC.
3. Roda a regra congelada; só trades com entrada no período de teste contam.
4. Estatística geral, por ano e na janela recente; baselines; veredito com a
   exigência de recência (DEGRADED se a vantagem não vale para o mercado atual).

    python scripts/run_oos_dukascopy.py --dukascopy D:/OneB/market-data/dukascopy-xau-2019-2026/normalized/XAUUSD_M5_2019-03-01_2026-09-26.csv.gz
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.baselines import PlainBreakout, random_entry_distribution, ready_signals  # noqa: E402
from app.execution_sim import CostModel, replay_ready_signals  # noqa: E402
from app.forward_stats import bootstrap_mean_ci, sample_size_note, summarize, verdict  # noqa: E402
from app.setups import build_setup, load_preregistered  # noqa: E402
from app.setups.base import resample_bars  # noqa: E402

COLUMNS = ["open", "high", "low", "close", "spread", "tick_volume"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_dukascopy(path: Path) -> pd.DataFrame:
    """Barras bid (convenção MT5) + spread em USD da abertura de cada barra."""
    raw = pd.read_csv(path)
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True).dt.tz_localize(None)
    raw = raw.drop_duplicates("timestamp").sort_values("timestamp").set_index("timestamp")
    frame = pd.DataFrame({
        "open": raw["bid_open"], "high": raw["bid_high"], "low": raw["bid_low"], "close": raw["bid_close"],
        "spread_usd": raw["spread_open"].clip(lower=0), "tick_volume": raw.get("volume", 0),
    }).dropna(subset=["open", "high", "low", "close"])
    bad = (frame["high"] < frame[["open", "close"]].max(axis=1)) | (frame["low"] > frame[["open", "close"]].min(axis=1))
    return frame[~bad], int(bad.sum())


def load_honorpro(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["timestamp"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_localize(None)
    return frame.drop_duplicates("timestamp").sort_values("timestamp").set_index("timestamp")


def _ready_utc(bars: pd.DataFrame, config: dict, offset_hours: float, start, end) -> list[dict]:
    cfg = {**config, "server_utc_offset_hours": offset_hours}
    m10 = resample_bars(bars[COLUMNS], int(cfg["timeframe_minutes"]), closed_before=bars.index[-1] + pd.Timedelta(minutes=5))
    out = []
    for signal in ready_signals(build_setup(cfg).run(m10)):
        at_utc = pd.Timestamp(signal["at"]) - pd.Timedelta(hours=offset_hours)
        if start <= at_utc < end:
            out.append({"at_utc": at_utc, "direction": signal["direction"]})
    return out


def validate_feed(duka: pd.DataFrame, honor: pd.DataFrame, rule: dict, spec: dict) -> dict:
    val = spec["feed_validation"]
    start, end = pd.Timestamp(val["period"]["from_inclusive"]), pd.Timestamp(val["period"]["to_exclusive"])
    crit = val["criteria"]
    candidates = []
    for offset in val["honorpro_offset_search_hours"]:
        shifted = honor.copy()
        shifted.index = shifted.index - pd.Timedelta(hours=offset)
        joined = duka[["close"]].join(shifted[["close"]], how="inner", lsuffix="_duka", rsuffix="_honor")
        joined = joined[(joined.index >= start) & (joined.index < end)]
        if len(joined) < 1000:
            candidates.append({"offset_hours": offset, "rows": len(joined), "corr": None})
            continue
        returns = joined.pct_change().dropna()
        candidates.append({
            "offset_hours": offset, "rows": len(joined),
            "corr": round(float(returns["close_duka"].corr(returns["close_honor"])), 5),
            "median_abs_close_diff": round(float((joined["close_duka"] - joined["close_honor"]).abs().median()), 4),
        })
    valid = [c for c in candidates if c["corr"] is not None]
    best = max(valid, key=lambda c: c["corr"]) if valid else None
    result = {"offset_candidates": candidates, "best_offset_hours": best["offset_hours"] if best else None}
    if best is None:
        return {**result, "passed": False, "reason": "sem sobreposição suficiente"}

    offset = best["offset_hours"]
    honor_utc = honor.copy()
    honor_utc.index = honor_utc.index - pd.Timedelta(hours=offset)
    window = honor_utc[(honor_utc.index >= start) & (honor_utc.index < end)]
    hourly_spread_usd = (window["spread"] * float(rule["point"])).groupby(window.index.hour).median()

    honor_ready = _ready_utc(honor, rule, offset, start, end)
    duka_bars = duka.assign(spread=duka["spread_usd"] / float(rule["point"]))
    duka_ready = _ready_utc(duka_bars, rule, 0, start, end)
    tol = pd.Timedelta(minutes=crit["ready_signal_tolerance_minutes"])
    matched = sum(
        any(d["direction"] == h["direction"] and abs(d["at_utc"] - h["at_utc"]) <= tol for d in duka_ready)
        for h in honor_ready
    )
    recall = matched / len(honor_ready) if honor_ready else None
    checks = {
        "m5_return_correlation": best["corr"] >= crit["m5_return_correlation_min"],
        "median_abs_close_diff": best["median_abs_close_diff"] <= crit["median_abs_close_diff_usd_max"],
        "ready_signal_recall": recall is not None and recall >= crit["ready_signal_recall_min"],
    }
    duka_window = duka[(duka.index >= start) & (duka.index < end)]
    return {
        **result,
        "correlation": best["corr"], "median_abs_close_diff_usd": best["median_abs_close_diff"],
        "honor_ready_signals": len(honor_ready), "duka_ready_signals": len(duka_ready), "signals_matched": matched,
        "ready_signal_recall": round(recall, 4) if recall is not None else None,
        "spread_median_usd": {"dukascopy": round(float(duka_window["spread_usd"].median()), 4),
                              "honorpro": round(float((window["spread"] * float(rule["point"])).median()), 4)},
        "honor_hourly_spread_usd": {int(k): round(float(v), 4) for k, v in hourly_spread_usd.items()},
        "checks": checks, "passed": all(checks.values()),
    }


def _source_gaps(normalized_path: Path) -> dict:
    """Dias que a própria fonte não tem (registrados pelo downloader com evidência)."""
    path = normalized_path.parent.parent / "source_gaps.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def yearly(trades: list[dict], bars: pd.DataFrame) -> dict:
    tr = pd.Series(bars["high"] - bars["low"])
    atr_pct = (tr.rolling(14).mean() / bars["close"] * 100).groupby(bars.index.year).mean()
    out = {}
    for year in sorted({pd.Timestamp(t["entry_at"]).year for t in trades}):
        rs = [t["r"] for t in trades if pd.Timestamp(t["entry_at"]).year == year]
        ci = bootstrap_mean_ci(rs)
        out[str(year)] = {"trades": len(rs), "expectancy_r": round(float(np.mean(rs)), 4),
                          "ci95": [round(ci[0], 4), round(ci[1], 4)] if ci else None,
                          "atr_m5_pct_of_price": round(float(atr_pct.get(year, np.nan)), 4)}
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dukascopy", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    rule, rule_sha = load_preregistered("gold_fakeout_open_v1")
    spec, spec_sha = load_preregistered("gold_fakeout_open_v1_oos_dukascopy")
    if spec["rule_sha256"] != rule_sha:
        raise SystemExit("A regra mudou desde o pré-registro do teste.")
    duka, bad_rows = load_dukascopy(args.dukascopy)
    honor_path = Path(spec["feed_validation"]["honorpro_bars"])
    honor = load_honorpro(honor_path)

    validation = validate_feed(duka, honor, rule, spec)
    hourly = validation.get("honor_hourly_spread_usd") or {}
    honor_floor = duka.index.hour.map(lambda h: hourly.get(int(h), 0.0)).to_numpy()
    spread_usd = np.maximum(duka["spread_usd"].to_numpy(), honor_floor)
    bars = duka.assign(spread=spread_usd / float(rule["point"]))[COLUMNS]

    cfg = {**rule, "server_utc_offset_hours": spec["data_overrides"]["server_utc_offset_hours"]}
    test_from, test_to = pd.Timestamp(spec["test_period"]["from_inclusive"]), pd.Timestamp(spec["test_period"]["to_exclusive"])
    m10 = resample_bars(bars, int(cfg["timeframe_minutes"]), closed_before=bars.index[-1] + pd.Timedelta(minutes=5))
    setup = build_setup(cfg)
    transitions = setup.run(m10)
    in_test = [s for s in ready_signals(transitions) if test_from <= pd.Timestamp(s["at"]) < test_to]
    costs = CostModel.from_config(cfg)
    trades, ignored = replay_ready_signals(bars, in_test, costs)
    trade_dicts = [t.to_dict() for t in trades]
    test_bars = bars[(bars.index >= test_from) & (bars.index < test_to)]
    sessions = int(pd.Index((test_bars.index - pd.Timedelta(hours=3)).date).nunique())
    summary = summarize(trade_dicts, sessions=sessions)

    plain_ready = [s for s in ready_signals(PlainBreakout(cfg).run(m10)) if test_from <= pd.Timestamp(s["at"]) < test_to]
    plain_trades, _ = replay_ready_signals(bars, plain_ready, costs)
    plain = summarize([t.to_dict() for t in plain_trades], sessions=sessions)
    random_dist = random_entry_distribution(test_bars, trades, cfg, costs, seeds=200)
    pct = None
    if summary["expectancy_r"] is not None and random_dist.get("expectancies"):
        pct = round(float(np.mean(np.asarray(random_dist["expectancies"]) <= summary["expectancy_r"])) * 100, 1)

    completed = [t for t in trade_dicts if t["outcome"] in ("TARGET", "STOP", "TIME_EXIT")]
    by_year = yearly(completed, test_bars)
    recent = spec["recency_requirement"]["recent_window"]
    recent_rs = [t["r"] for t in completed
                 if pd.Timestamp(recent["from_inclusive"]) <= pd.Timestamp(t["entry_at"]) < pd.Timestamp(recent["to_exclusive"])]
    recent_ci = bootstrap_mean_ci(recent_rs)
    recent_stats = {"trades": len(recent_rs), "expectancy_r": round(float(np.mean(recent_rs)), 4) if recent_rs else None,
                    "ci95": [round(recent_ci[0], 4), round(recent_ci[1], 4)] if recent_ci else None}

    decision = verdict(summary, {"min_sessions": 250, "min_trades": 100}, baseline_p95=random_dist.get("p95"))
    if not validation["passed"]:
        decision = {**decision, "status": "DESCRIPTIVE_ONLY",
                    "reason": "Feed Dukascopy reprovado na validação contra a HonorPro; resultado só descritivo. " + decision["reason"]}
    elif decision["status"] == "PASSED":
        years_negative = [y for y, v in by_year.items() if v["ci95"] and v["ci95"][1] < 0]
        if not recent_rs or recent_stats["expectancy_r"] <= 0 or years_negative:
            decision = {**decision, "status": "DEGRADED",
                        "reason": f"Média histórica positiva, mas não vale para o mercado atual (janela recente {recent_stats['expectancy_r']}R; anos negativos {years_negative})."}

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "test": spec["test"], "spec_sha256": spec_sha, "rule_sha256": rule_sha, "setup_version": setup.version,
        "data": {"dukascopy": str(args.dukascopy), "dukascopy_sha256": sha256(args.dukascopy), "rows": len(duka),
                 "invalid_ohlc_rows_dropped": bad_rows, "first": duka.index[0].isoformat(), "last": duka.index[-1].isoformat(),
                 "honorpro": str(honor_path), "honorpro_sha256": sha256(honor_path), "test_sessions": sessions,
                 "sessions": sessions,
                 "clock": "VERIFIED" if validation["passed"] else "UNVERIFIED",  # feed UTC; offset HonorPro estimado pelos dados
                 "source_gaps": _source_gaps(args.dukascopy)},
        "feed_validation": validation,
        "signals_in_test": len(in_test), "signals_ignored": dict(Counter(i["reason"] for i in ignored)),
        "summary": summary, "by_year": by_year, "recent_window": recent_stats,
        "baselines": {"random_entry": {k: v for k, v in random_dist.items() if k != "expectancies"},
                      "strategy_percentile_vs_random": pct,
                      "plain_breakout": {k: plain[k] for k in ("completed_trades", "expectancy_r", "expectancy_ci95", "win_rate", "profit_factor")}},
        "verdict": decision, "sample_size": sample_size_note(summary),
        "trades": trade_dicts,
        "scope": spec["scope_of_conclusion"],
    }
    output = args.output or ROOT / "output" / "setup_research" / f"gold_fakeout_open_v1_oos_dukascopy_{datetime.now(timezone.utc):%Y%m%d}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    brief = {k: report[k] for k in ("data", "signals_in_test", "signals_ignored", "by_year", "recent_window", "baselines", "verdict")}
    brief["feed_validation"] = {k: v for k, v in validation.items() if k != "honor_hourly_spread_usd"}
    brief["summary"] = {k: v for k, v in summary.items() if not k.startswith("by_")}
    print(json.dumps(brief, ensure_ascii=False, indent=2, default=str))
    print(f"\nRelatório: {output}")


if __name__ == "__main__":
    main()
