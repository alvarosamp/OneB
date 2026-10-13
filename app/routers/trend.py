"""Leitura de tendência (1, 3 e 12 meses) dos ativos acompanhados.

A direção vem de app/trend.reading() sobre o histórico diário do app. O selo de
evidência vem do resultado do teste pré-registrado tsmom_v1, resumido em
app/research_results/tsmom_v1.json (gerado por scripts/run_tsmom.py). Enquanto o
teste não roda, ou se ele não for aprovado, a leitura é só descritiva.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends

from app import response_cache, trend
from app.auth import get_current_user
from app.market_data import service as market_data

router = APIRouter(prefix="/api/trend", tags=["trend"], dependencies=[Depends(get_current_user)])

RESULT_PATH = Path(__file__).resolve().parents[1] / "research_results" / "tsmom_v1.json"
SENSITIVITY_PATH = RESULT_PATH.with_name("tsmom_v1_sensitivity.json")

ASSETS = [
    {"key": "NAS100", "symbol": "NQ=F", "label": "Nasdaq 100", "instrument": "usatechidxusd", "class": "equity_index"},
    {"key": "SPX500", "symbol": "ES=F", "label": "S&P 500", "instrument": "usa500idxusd", "class": "equity_index"},
    {"key": "XAUUSD", "symbol": "GC=F", "label": "Ouro", "instrument": "xauusd", "class": "commodity"},
    {"key": "WTI", "symbol": "CL=F", "label": "Petróleo WTI", "instrument": "lightcmdusd", "class": "commodity"},
    {"key": "EURUSD", "symbol": "EURUSD=X", "label": "Euro/dólar", "instrument": "eurusd", "class": "fx"},
]


def evidence() -> dict:
    if not RESULT_PATH.exists():
        return {"status": "PENDING", "reason": "O teste pré-registrado tsmom_v1 ainda não foi executado.", "as_evidence": False}
    r = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    status = r["verdict"]["status"]
    return {"status": status, "reason": r["verdict"]["reason"], "as_evidence": status == "PASSED",
            "test": r["test"], "generated_at": r["generated_at"], "primary": r["primary_combined"],
            "recent": r["recent_window"], "by_class": r["by_class"], "beyond_long_only": r["beyond_long_only"],
            "by_instrument": r["by_instrument"], "universe_size": len(r["universe_used"]), "sensitivity": _sensitivity()}


def _sensitivity() -> dict | None:
    """Universo completo com séries gratuitas (só descritivo; não muda o veredito primário)."""
    if not SENSITIVITY_PATH.exists():
        return None
    full = json.loads(SENSITIVITY_PATH.read_text(encoding="utf-8"))["plus_all_6"]
    return {"universe_size": len(full["universe"]), "combined": full["combined"], "status": full["verdict"]["status"]}


def _reading(asset: dict) -> dict:
    bars = market_data.get_bars(asset["symbol"], period="2y", interval="1d")
    if bars is None or bars.empty or len(bars) < 260:
        return {**{k: asset[k] for k in ("key", "symbol", "label")}, "available": False}
    frame = pd.DataFrame({"close": bars["close"].astype(float).to_numpy(), "spread": 0.0},
                         index=pd.DatetimeIndex(bars.index).tz_localize(None).normalize())
    return {**{k: asset[k] for k in ("key", "symbol", "label", "class", "instrument")}, "available": True, **trend.reading(frame)}


@router.get("/readings")
def readings():
    # Histórico diário muda uma vez por dia; 5 min de cache poupa 5 consultas por abertura de página.
    return response_cache.cached("trend:readings", 300, _readings)


def _readings():
    ev = evidence()
    out = []
    for asset in ASSETS:
        try:
            item = _reading(asset)
        except Exception:  # fonte de dados fora do ar não derruba os outros ativos
            item = {**{k: asset[k] for k in ("key", "symbol", "label")}, "available": False}
        if ev.get("by_instrument") and asset["instrument"] in ev["by_instrument"]:
            item["backtest_instrument"] = ev["by_instrument"][asset["instrument"]]
        out.append(item)
    return {"evidence": {k: v for k, v in ev.items() if k != "by_instrument"}, "assets": out,
            "note": "Leitura de preço, não ordem. A direção só conta como evidência se o teste pré-registrado for aprovado."}
