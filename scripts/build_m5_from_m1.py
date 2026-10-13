"""Monta o M5 normalizado a partir do M1 normalizado já baixado (sem rede).

    python scripts/build_m5_from_m1.py D:/OneB/market-data/dukascopy-xau-2019-2026 XAUUSD

Uso: o M5 do XAUUSD foi invalidado pela reverificação de 07/10/2026 (7 dias com lacuna
falsa no lado ask), e a Dukascopy bloqueou o nosso IP antes de refazer. O M1 cobre o
mesmo período. Os dias sem ask continuam fora (bid e ask são cruzados como no
normalize_pair), e ficam listados na proveniência.

Validação: compara com o M5 anterior (*.pre_reverify) nas barras em comum.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

AGG = {"open": "first", "high": "max", "low": "min", "close": "last"}


def side_m5(m1: pd.DataFrame, side: str) -> pd.DataFrame:
    cols = {f"{side}_{k}": v for k, v in AGG.items()}
    return m1[list(cols)].resample("5min", label="left", closed="left").agg(cols)


def build(m1: pd.DataFrame) -> pd.DataFrame:
    m1 = m1.set_index("timestamp").sort_index()
    out = pd.concat([side_m5(m1, "bid"), side_m5(m1, "ask"),
                     m1["volume"].resample("5min", label="left", closed="left").sum().rename("volume")], axis=1)
    out = out.dropna(subset=["bid_open", "ask_open"])
    for field in AGG:
        out[field] = (out[f"bid_{field}"] + out[f"ask_{field}"]) / 2
    out["spread_open"] = out["ask_open"] - out["bid_open"]
    out["spread_close"] = out["ask_close"] - out["bid_close"]
    cols = ["open", "high", "low", "close", "volume", "bid_open", "bid_high", "bid_low", "bid_close",
            "ask_open", "ask_high", "ask_low", "ask_close", "spread_open", "spread_close"]
    return out[cols].rename_axis("timestamp").reset_index()


def main() -> None:
    root, instrument = Path(sys.argv[1]), sys.argv[2]
    norm = root / "normalized"
    m1_path = next(norm.glob(f"{instrument}_M1_*.csv.gz"))
    m1 = pd.read_csv(m1_path)
    m1["timestamp"] = pd.to_datetime(m1["timestamp"], utc=True)
    m5 = build(m1)
    dest = norm / m1_path.name.replace("_M1_", "_M5_")
    report = {"built_at": datetime.now(timezone.utc).isoformat(), "from": m1_path.name,
              "m1_sha256": hashlib.sha256(m1_path.read_bytes()).hexdigest(), "rows": len(m5)}
    old = dest.with_name(dest.name + ".pre_reverify")
    if old.exists():
        prev = pd.read_csv(old, compression="gzip")
        prev["timestamp"] = pd.to_datetime(prev["timestamp"], utc=True)
        both = m5.merge(prev, on="timestamp", suffixes=("", "_old"))
        diff = pd.concat([(both[c] - both[f"{c}_old"]).abs() for c in ("bid_open", "bid_high", "bid_low", "bid_close",
                                                                        "ask_open", "ask_close")], axis=1).max(axis=1)
        report["vs_previous_m5"] = {"previous_rows": len(prev), "common": len(both),
                                    "identical_share": round(float((diff < 1e-6).mean()), 5),
                                    "max_abs_diff": float(diff.max()), "p999_abs_diff": float(diff.quantile(0.999))}
    days = pd.Series(1, index=m5["timestamp"].dt.date).groupby(level=0).size()
    weekdays = pd.bdate_range(m5["timestamp"].min().date(), m5["timestamp"].max().date()).date
    report["weekdays_without_bars"] = [str(d) for d in weekdays if d not in days.index]
    m5.to_csv(dest, index=False, compression="gzip")
    report["output"], report["sha256"] = str(dest), hashlib.sha256(dest.read_bytes()).hexdigest()
    dest.with_suffix("").with_suffix(".provenance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "weekdays_without_bars"}, indent=1))
    print("dias úteis sem barras:", report["weekdays_without_bars"])


if __name__ == "__main__":
    main()
