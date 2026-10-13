"""Converte blocos M1 bid do Dukascopy no CSV lido por mql5/Scripts/Research/ImportCustomRates.mq5.

Relógio: UTC -> horário típico de servidor MT5 (UTC+3 durante o horário de verão
dos EUA, UTC+2 fora dele), conforme o pré-registro gold_fakeout_ex5_oos_dukascopy.
O spread gravado é a mediana do Dukascopy e não afeta os sinais do indicador.

    python scripts/build_custom_symbol_csv.py --start 2019-01-01 --end 2026-09-26
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

CHUNKS = Path(r"D:\OneB\market-data\dukascopy-xau-2019-2026\raw\chunks")
COMMON_FILES = Path(r"C:\Users\vish8\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
NEW_YORK = ZoneInfo("America/New_York")


def server_offset_hours(utc_index: pd.DatetimeIndex) -> pd.Series:
    """3 h quando Nova York está em horário de verão, senão 2 h."""
    local = utc_index.tz_localize("UTC").tz_convert(NEW_YORK)
    dst = pd.Series([bool(ts.dst()) for ts in local], index=utc_index)
    return dst.map({True: 3, False: 2})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--spread-points", type=int, default=37)
    parser.add_argument("--output", type=Path, default=COMMON_FILES / "XAUUSD_dk_M1.csv")
    args = parser.parse_args()
    files = []
    for path in sorted(CHUNKS.glob("XAUUSD_bid_M1_*.csv")):
        a, b = re.search(r"_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.csv$", path.name).groups()
        if b > args.start and a < args.end:
            files.append(path)
    if not files:
        raise SystemExit("Nenhum bloco M1 bid no intervalo.")
    frame = pd.concat([pd.read_csv(f) for f in files]).drop_duplicates("timestamp").sort_values("timestamp")
    utc = pd.to_datetime(frame["timestamp"], unit="ms")
    keep = (utc >= pd.Timestamp(args.start)) & (utc < pd.Timestamp(args.end))
    frame, utc = frame[keep.to_numpy()], utc[keep]
    offsets = server_offset_hours(pd.DatetimeIndex(utc)).to_numpy()
    server = utc + pd.to_timedelta(offsets, unit="h")
    out = pd.DataFrame({
        # Segundos explícitos: astype("int64") depende da unidade do datetime (ms/us/ns).
        "time": ((server - pd.Timestamp("1970-01-01")) // pd.Timedelta(seconds=1)).astype("int64").to_numpy(),
        "open": frame["open"].to_numpy(), "high": frame["high"].to_numpy(),
        "low": frame["low"].to_numpy(), "close": frame["close"].to_numpy(),
        "tick_volume": frame["volume"].fillna(0).round().astype("int64").clip(lower=1).to_numpy(),
        "spread": args.spread_points,
    })
    lo, hi = pd.Timestamp(args.start).timestamp() - 86400, pd.Timestamp(args.end).timestamp() + 86400
    if not (out["time"].min() >= lo and out["time"].max() <= hi):
        raise SystemExit(f"Epoch fora do intervalo pedido: {out['time'].min()}..{out['time'].max()}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    meta = {"rows": len(out), "first_server": str(server.iloc[0]), "last_server": str(server.iloc[-1]),
            "source_chunks": [f.name for f in files], "offset_rule": "UTC+3 em DST dos EUA, senão UTC+2", "sha256": digest}
    args.output.with_suffix(".manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in meta.items() if k != "source_chunks"}, indent=2))


if __name__ == "__main__":
    main()
