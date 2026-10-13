"""Confere o leitor do feed (dukascopy_feed) contra arquivos já baixados em D:.

    python scripts/calibrate_dukascopy_feed.py

Para cada instrumento: velas d1 de 2025 (bid) do feed contra o arquivo já baixado.
Escala errada aparece como razão em potência de 10; a casa decimal sugerida é impressa.
Também compara um dia de M5 (EURUSD e NAS100) com os brutos intradiários.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dukascopy_feed as feed  # noqa: E402

DATA = Path(r"D:\OneB\market-data")


def compare(ours: pd.DataFrame, ref: pd.DataFrame, cols=("open", "high", "low", "close")) -> dict:
    m = ours.merge(ref, on="timestamp", suffixes=("", "_ref"))
    out = {"feed": len(ours), "ref": len(ref), "common": len(m)}
    if len(m):
        ratio = (m["close"] / m["close_ref"]).median()
        out["power10"] = round(math.log10(ratio)) if ratio > 0 else None
        rel = pd.concat([(m[c] - m[f"{c}_ref"]).abs() / m[f"{c}_ref"].abs() for c in cols], axis=1).max(axis=1)
        out["max_rel_diff"] = float(rel.max())
        out["identical"] = round(float((rel < 1e-9).mean()), 4)
    return out


def acceptable(r: dict, ref_trading: int) -> bool:
    """Mesma escala, 95% das velas idênticas, nenhuma diferença acima de 0,5% e cobertura da referência."""
    return (r.get("power10") == 0 and r.get("identical", 0) >= 0.95 and r.get("max_rel_diff", 1) < 0.005
            and r["common"] >= 0.98 * ref_trading)


def main() -> None:
    bad = 0
    for inst in sorted(feed.DECIMALS):
        ref_path = DATA / "dukascopy-daily" / "raw" / f"{inst}_bid_2025.csv"
        if not ref_path.exists() or ref_path.stat().st_size == 0:
            print(f"{inst:15s} sem referência")
            continue
        ref = pd.read_csv(ref_path)
        ours = feed.candles(inst, "bid", "d1", "2025-01-01", "2026-01-01")
        r = compare(ours, ref)
        ok = acceptable(r, int((ref["high"] > ref["low"]).sum()))
        bad += not ok
        hint = "" if ok or r.get("power10") is None else f"  -> DECIMALS = {feed.DECIMALS[inst] - r['power10']}"
        print(f"{inst:15s} {'OK ' if ok else 'ERR'} {r}{hint}", flush=True)
    for name, inst, raw in [
        ("EURUSD", "eurusd", DATA / "dukascopy-eurusd-2019-2026" / "raw" / "EURUSD_bid_M5_2019-03-01_2026-09-26.csv"),
        ("NAS100", "usatechidxusd", next((DATA / "dukascopy-nas100-2019-2026" / "raw").glob("NAS100_bid_M5_*.csv"), None)),
    ]:
        if raw is None:
            continue
        ours = feed.candles(inst, "bid", "m5", "2024-01-10", "2024-01-11")
        lo, hi = ours["timestamp"].min(), ours["timestamp"].max()
        ref = pd.read_csv(raw, usecols=["timestamp", "open", "high", "low", "close", "volume"])
        ref = ref[(ref["timestamp"] >= lo) & (ref["timestamp"] <= hi)]
        r = compare(ours, ref)
        r["volume_identical"] = round(float((ours.merge(ref, on="timestamp")["volume_x"] == ours.merge(ref, on="timestamp")["volume_y"]).mean()), 4)
        bad += not acceptable(r, int((ref["high"] > ref["low"]).sum()))
        print(f"M5 {name}: {r}", flush=True)
    print("FALHAS:", bad)


if __name__ == "__main__":
    main()
