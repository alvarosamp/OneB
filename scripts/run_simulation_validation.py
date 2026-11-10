from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("MARKET_DATA_CACHE_ONLY", "true")

from app import paper_simulator
from app.market_data import service as market_data_service

SYMBOLS = ["AAPL", "MSFT", "NVDA", "SNAP"]
REPORT_PATH = Path(os.getenv("SIM_VALIDATION_REPORT", "data/simulation_validation_report.json"))
DEEP_CALIBRATION = os.getenv("SIM_VALIDATION_DEEP_CALIBRATION", "false").lower() == "true"


def _market_data_check(symbols: list[str]) -> list[dict]:
    rows = []
    for symbol in symbols:
        history = market_data_service.get_bars(symbol, period=paper_simulator.MARKET_HISTORY_PERIOD, interval="1d")
        rows.append(
            {
                "symbol": symbol,
                "rows": int(len(history)),
                "has_ohlcv": bool(
                    not history.empty
                    and {"open", "high", "low", "close", "volume"}.issubset(set(history.columns))
                    and history[["open", "high", "low", "close", "volume"]].dropna().shape[0] >= 90
                ),
                "last_close": None if history.empty else round(float(history["close"].dropna().iloc[-1]), 2),
            }
        )
    return rows


def build_report(symbols: list[str] | None = None) -> dict:
    symbols = symbols or SYMBOLS
    state = paper_simulator._load_state()
    prepared = {}
    selected_filter = None
    if DEEP_CALIBRATION:
        selected_filter, calibration, prepared = paper_simulator.calibrate(symbols)
        portfolio_value = paper_simulator._portfolio_value(state, prepared)
    else:
        calibration = {
            "status": "skipped",
            "reason": "Validacao rapida usa cache local; defina SIM_VALIDATION_DEEP_CALIBRATION=true para recalibrar.",
        }
        portfolio_value = float(state.get("cash", 0.0))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbols": symbols,
        "mode": "deep_calibration" if DEEP_CALIBRATION else "quick_cache_check",
        "initial_capital": float(state.get("initial_capital", 200.0)),
        "cash": float(state.get("cash", 0.0)),
        "open_positions": state.get("positions", {}),
        "closed_trades": state.get("closed_trades", []),
        "portfolio_value": portfolio_value,
        "market_data": _market_data_check(symbols),
        "calibration": calibration,
        "can_trade_now": selected_filter is not None,
        "decision_rule": "Opera somente se precisao historica >= 58%, retorno medio futuro > 0 e sinal atual passar no filtro.",
        "risk_rule": "Compra no maximo uma posicao, usa a banca disponivel, stop em 1 ATR e alvo em 2 ATR.",
    }


def main() -> None:
    report = build_report()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
