"""Confere a especificação da corretora usada pelo OneB contra o terminal MT5 (só leitura, nenhuma ordem).

    python scripts/check_broker_specs.py [--write] [--terminal "C:/Program Files/Honor Pro MT5 Terminal/terminal64.exe"]

A HonorPro já mudou o lote mínimo do US100.s sem aviso (1,0 em 25/09/2026, 0,1 em 14/10/2026).
Rode antes de cada deploy: qualquer diferença em contrato, lote mínimo, passo ou spread mediano
(barras M5 dos últimos 60 dias) aparece aqui. Com --write, grava os valores do MT5 em
configs/broker/honorpro.json (com a data e o histórico da mudança); depois rode os testes e faça o deploy.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.routers.asset_brief import BROKER, BROKER_FILE, BROKER_VERIFIED_AT  # noqa: E402


def main() -> int:
    import MetaTrader5 as mt5

    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal", default=r"C:\Program Files\Honor Pro MT5 Terminal\terminal64.exe")
    parser.add_argument("--write", action="store_true", help="grava os valores do MT5 em configs/broker/honorpro.json")
    args = parser.parse_args()
    if not mt5.initialize(path=args.terminal, timeout=60_000):
        print("MT5 não inicializou:", mt5.last_error())
        return 2
    diffs = 0
    updated: dict[str, dict] = {}
    changes: list[str] = []
    try:
        end = datetime.now(timezone.utc)
        for key, spec in BROKER.items():
            info = mt5.symbol_info(spec["symbol"])
            if info is None:
                print(f"{key}: símbolo {spec['symbol']} não encontrado no terminal (mantido como está; confira o Market Watch)")
                updated[key] = dict(spec)
                diffs += 1
                continue
            rates = mt5.copy_rates_range(spec["symbol"], mt5.TIMEFRAME_M5, end - timedelta(days=60), end)
            spread = float(pd.Series(rates["spread"]).median() * info.point) if rates is not None and len(rates) else None
            live = {"contract_size": info.trade_contract_size, "volume_min": info.volume_min, "volume_step": info.volume_step,
                    "spread_points": round(spread, 6) if spread is not None else None}
            updated[key] = {**spec, **{k: v for k, v in live.items() if v is not None}}
            for field, value in live.items():
                ours = spec.get(field)
                same = ours == value if field != "spread_points" else (ours is not None and value is not None and abs(ours - value) <= 0.15 * max(ours, value))
                if not same:
                    diffs += 1
                    changes.append(f"{spec['symbol']} {field} {ours} -> {value}")
                print(f"{'OK ' if same else 'DIFERENTE'} {key:7} {field:14} OneB={ours} MT5={value}")
    finally:
        mt5.shutdown()
    print(f"\nEspecificação do OneB conferida em {BROKER_VERIFIED_AT}. Diferenças: {diffs}")
    if args.write and updated:
        today = datetime.now(timezone.utc).date().isoformat()
        data = json.loads(BROKER_FILE.read_text(encoding="utf-8"))
        data["assets"], data["verified_at"] = updated, today
        if changes:
            data.setdefault("history", []).append(f"{today}: " + "; ".join(changes))
        BROKER_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"Gravado em {BROKER_FILE} (verificado em {today}).")
        return 0
    return 1 if diffs else 0


if __name__ == "__main__":
    raise SystemExit(main())
