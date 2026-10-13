"""Executa o estudo pré-registrado calendar_v1 (influência do calendário macro).

    python scripts/run_calendar_study.py NAS100 SPX500 EURUSD

Cada ativo é uma família própria (BH por ativo), então ativos podem ser rodados
assim que seus dados M5 estiverem completos. Relatório completo em
D:/OneB/research/calendar_v1/, resumo versionado em app/research_results/calendar_v1.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import calendar_study as cs  # noqa: E402
from app.research_paths import RESEARCH_ROOT  # noqa: E402
from app.setups import load_preregistered  # noqa: E402

MARKET = Path(r"D:\OneB\market-data")
FILES = {
    "NAS100": MARKET / "dukascopy-nas100-2019-2026/normalized/NAS100_M5_2019-03-01_2026-09-26.csv.gz",
    "SPX500": MARKET / "dukascopy-spx500-2019-2026/normalized/SPX500_M5_2019-03-01_2026-09-26.csv.gz",
    "XAUUSD": MARKET / "dukascopy-xau-2019-2026/normalized/XAUUSD_M5_2019-03-01_2026-09-26.csv.gz",
    "EURUSD": MARKET / "dukascopy-eurusd-2019-2026/normalized/EURUSD_M5_2019-03-01_2026-09-26.csv.gz",
    "WTI": MARKET / "dukascopy-wti-2019-2026/normalized/WTI_M5_2019-03-01_2026-09-26.csv.gz",
}
SUMMARY = ROOT / "app" / "research_results" / "calendar_v1.json"


def load(asset: str) -> pd.DataFrame:
    d = pd.read_csv(FILES[asset], usecols=["timestamp", "close", "spread_close"])
    d.index = pd.to_datetime(d["timestamp"], utc=True)
    return d.rename(columns={"spread_close": "spread"})[["close", "spread"]]


def main() -> None:
    spec, spec_sha = load_preregistered("calendar_v1")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assets", nargs="+", choices=spec["data"]["assets"])
    args = parser.parse_args()
    events_path = ROOT / spec["events_file"]["path"]
    digest = hashlib.sha256(events_path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    if not digest.startswith(spec["events_file"]["sha256_prefix"]):
        raise SystemExit(f"Lista de eventos alterada após o registro ({digest[:12]}).")
    events = cs.load_events(events_path)
    event_days = {t.tz_convert(cs.NEW_YORK).date() for _, t in events}
    fomc_days = [t.tz_convert(cs.NEW_YORK).date() for k, t in events if k == "FOMC"]
    summary = json.loads(SUMMARY.read_text(encoding="utf-8")) if SUMMARY.exists() else {"test": spec["test"], "assets": {}}
    out_dir = RESEARCH_ROOT / "calendar_v1"
    out_dir.mkdir(parents=True, exist_ok=True)
    for asset in args.assets:
        if not FILES[asset].exists():
            print(f"{asset}: arquivo M5 ainda não existe ({FILES[asset].name}); pulei.")
            continue
        m5 = load(asset)
        close, spread = cs.bar_end_series(m5)
        lo, hi = close.index.min(), close.index.max()
        evs = [(k, t) for k, t in events if lo <= t - pd.Timedelta(hours=2) and t + pd.Timedelta(hours=3) <= hi]
        vol = cs.volatility(close, evs, event_days)
        h1_p = {k: v["post30"]["p_le_1"] for k, v in vol.items() if "p_le_1" in v.get("post30", {})}
        h1_pass = cs.bh(h1_p)
        for k in vol:
            vol[k]["H1_passed"] = bool(h1_pass.get(k, False))
        dirn = cs.direction(close, spread, evs)
        h2_p = {k: v["p_two_sided"] for k, v in dirn.items() if "p_two_sided" in v}
        h2_pass = cs.bh(h2_p)
        for k in dirn:
            dirn[k]["H2_significant"] = bool(h2_pass.get(k, False))
        report = {"generated_at": datetime.now(timezone.utc).isoformat(), "test": spec["test"], "spec_sha256": spec_sha,
                  "asset": asset, "events_in_range": len(evs), "H1_volatility": vol, "H2_direction": dirn}
        if asset in ("SPX500", "NAS100"):
            report["H3_pre_fomc"] = cs.pre_fomc(close, [d for d in fomc_days if lo.date() < d < hi.date()])
        (out_dir / f"calendar_v1_{asset}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        summary["generated_at"] = report["generated_at"]
        summary["spec_sha256"] = spec_sha
        summary["assets"][asset] = report
        SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n== {asset} ({len(evs)} eventos)")
        for k, v in vol.items():
            p30 = v.get("post30", {})
            print(f"  {k:5s} post30 razão {p30.get('median_ratio')} IC {p30.get('ci95')} n={p30.get('events')} H1={v['H1_passed']} | "
                  f"post5 {v.get('post5', {}).get('median_ratio')} pre60 {v.get('pre60', {}).get('median_ratio')} post120 {v.get('post120', {}).get('median_ratio')} | "
                  f"direção {dirn[k].get('mean_bps')}bps IC {dirn[k].get('ci95_bps')} {dirn[k].get('reading')}")
        if "H3_pre_fomc" in report:
            print("  pré-FOMC:", report["H3_pre_fomc"])


if __name__ == "__main__":
    main()
