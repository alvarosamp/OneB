"""Coletor + executor shadow contínuo (plano Fase 1.1/1.2). SOMENTE LEITURA.

A cada ciclo:
1. lê as barras M5 fechadas e os ticks bid/ask novos do terminal MT5 local
   (já autenticado; este script nunca chama funções de ordem);
2. grava os ticks em arquivo diário com manifest + SHA256 (evidência bruta);
3. passa as barras pelo ShadowEngine (mesma lógica do replay);
4. grava cada transição no ledger SHADOW (hash encadeado).

    python scripts/run_shadow.py --setup gold_fakeout_open_v1
    python scripts/run_shadow.py --setup gold_fakeout_open_v1 --once     # um ciclo, para testar

Rodar em segundo plano durante a sessão (ou como serviço). Ctrl+C encerra.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import SessionLocal, init_db  # noqa: E402
from app.models import OpportunityEvent  # noqa: E402
from app.opportunity import approval_for  # noqa: E402
from app.opportunity_ledger import record_transition  # noqa: E402
from app.setups import load_preregistered  # noqa: E402
from app.shadow import ShadowEngine  # noqa: E402

DEFAULT_OUT = Path(r"D:\OneB\market-data\mt5\shadow")


def _rates_frame(rates) -> pd.DataFrame:
    frame = pd.DataFrame(rates)
    frame["timestamp"] = pd.to_datetime(frame["time"], unit="s")
    frame = frame.set_index("timestamp")
    return frame[["open", "high", "low", "close", "spread", "tick_volume"]].astype(float)


def _append_ticks(mt5, symbol: str, since_msc: int, out_dir: Path) -> int:
    """Grava ticks desde `since_msc` (tempo bruto do servidor) e devolve o último time_msc."""
    start = datetime.fromtimestamp(since_msc / 1000 + 0.001, tz=timezone.utc)
    ticks = mt5.copy_ticks_from(symbol, start, 200_000, mt5.COPY_TICKS_INFO)
    if ticks is None or len(ticks) == 0:
        return since_msc
    frame = pd.DataFrame(ticks)
    frame = frame[frame["time_msc"] > since_msc]
    if frame.empty:
        return since_msc
    for day, chunk in frame.groupby(pd.to_datetime(frame["time_msc"], unit="ms").dt.date):
        path = out_dir / f"{symbol}_ticks_{day}.csv"
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            if new:
                writer.writerow(["time_msc", "bid", "ask"])
            writer.writerows(chunk[["time_msc", "bid", "ask"]].itertuples(index=False, name=None))
    return int(frame["time_msc"].max())


def _write_manifest(out_dir: Path, symbol: str, config_sha: str) -> None:
    files = sorted(out_dir.glob(f"{symbol}_ticks_*.csv"))
    manifest = {
        "symbol": symbol, "generated_at": datetime.now(timezone.utc).isoformat(), "preregistration_sha256": config_sha,
        "timestamp_basis": "raw_mt5_server_time", "read_only": True,
        "files": [{"name": f.name, "sha256": hashlib.sha256(f.read_bytes()).hexdigest(), "bytes": f.stat().st_size} for f in files],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _open_position_from_ledger(db, setup: str) -> dict | None:
    """Reconstrói a posição shadow aberta após reinício do processo."""
    last = db.query(OpportunityEvent).filter(OpportunityEvent.mode == "SHADOW", OpportunityEvent.setup == setup) \
        .order_by(OpportunityEvent.id.desc()).first()
    if last is None or last.state not in ("READY_TO_ENTER", "POSITION_OPEN"):
        return None
    events = db.query(OpportunityEvent).filter(OpportunityEvent.opportunity_id == last.opportunity_id).order_by(OpportunityEvent.id).all()
    ready = next((e for e in events if e.state == "READY_TO_ENTER"), None)
    if ready is None:
        return None
    return {
        "opportunity_id": last.opportunity_id, "direction": ready.direction,
        "signal_at": ready.event_at.replace(tzinfo=None).isoformat(), "stop": float(ready.payload["stop"]),
        "target_r": float(ready.payload["target_r"]), "max_hold_minutes": int(ready.payload["max_hold_minutes"]),
        "opened": last.state == "POSITION_OPEN",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup", default="gold_fakeout_open_v1")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--interval", type=int, default=20, help="segundos entre ciclos")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    import MetaTrader5 as mt5

    config, config_sha = load_preregistered(args.setup)
    symbol = config["symbol"]
    if not mt5.initialize():
        raise SystemExit(f"MT5 não inicializou: {mt5.last_error()}")
    if not mt5.symbol_select(symbol, True):
        raise SystemExit(f"Símbolo indisponível: {symbol}")
    out_dir = args.out / config["setup"]
    out_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    db = SessionLocal()
    engine = ShadowEngine(config, open_position=_open_position_from_ledger(db, config["setup"]))
    approval = approval_for(symbol)
    tick = mt5.symbol_info_tick(symbol)
    last_msc = int(tick.time_msc) - 60_000 if tick else 0
    print(f"shadow {args.setup} {symbol} approval={approval.value} out={out_dir}")
    try:
        while True:
            tick = mt5.symbol_info_tick(symbol)
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, engine.min_history_m5_bars)
            if tick is None or rates is None or len(rates) == 0:
                print("sem dados do terminal:", mt5.last_error())
            else:
                now = pd.Timestamp(int(tick.time_msc), unit="ms")
                m5 = _rates_frame(rates)
                m5 = m5[m5.index + timedelta(minutes=5) <= now]  # descarta a barra em formação
                last_msc = _append_ticks(mt5, symbol, last_msc, out_dir)
                for transition in engine.on_bars(m5, now):
                    record_transition(db, transition, setup=config["setup"], setup_version=engine.setup.version,
                                      symbol=symbol, mode="SHADOW", approval=approval)
                    print(transition.at, transition.from_state.value, "->", transition.to_state.value, transition.reason)
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        _write_manifest(out_dir, symbol, config_sha)
        db.close()
        mt5.shutdown()


if __name__ == "__main__":
    main()
