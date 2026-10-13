"""Risco de calendário: quanto a volatilidade costuma multiplicar depois de cada tipo de evento.

Lê o resumo do estudo pré-registrado calendar_v1 (app/research_results/calendar_v1.json,
gerado por scripts/run_calendar_study.py). Só entram pares evento x ativo aprovados
em H1 (IC 95% da razão mediana acima de 1, com correção BH por ativo).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

SUMMARY = Path(__file__).resolve().parent / "research_results" / "calendar_v1.json"
ASSET_LABEL = {"NAS100": "Nasdaq", "SPX500": "S&P 500", "XAUUSD": "Ouro", "EURUSD": "Euro/dólar", "WTI": "Petróleo"}


def event_type(name: str) -> str | None:
    n = name.upper()
    if "FOMC" in n or "FEDERAL FUNDS" in n or "INTEREST RATE DECISION" in n:
        return "FOMC"
    if "NFP" in n or "NONFARM" in n or "EMPLOYMENT SITUATION" in n:
        return "NFP"
    if "CPI" in n or "CONSUMER PRICE" in n:
        return "CPI"
    if "PCE" in n or "PERSONAL INCOME" in n:
        return "PCE"
    if "GDP" in n or "GROSS DOMESTIC" in n:
        return "GDP"
    return None


@lru_cache(maxsize=1)
def _summary(mtime: float) -> dict:
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def risk_for(name: str) -> dict | None:
    """Multiplicadores de volatilidade por ativo para o tipo do evento, ou None se não houver estudo."""
    kind = event_type(name)
    if kind is None or not SUMMARY.exists():
        return None
    data = _summary(SUMMARY.stat().st_mtime)
    assets = []
    for asset, report in data.get("assets", {}).items():
        vol = report["H1_volatility"].get(kind)
        if not vol or not vol.get("H1_passed"):
            continue
        assets.append({"asset": asset, "label": ASSET_LABEL.get(asset, asset),
                       **{w: vol[w].get("median_ratio") for w in ("pre60", "post5", "post30", "post120") if w in vol},
                       "post30_ci95": vol["post30"].get("ci95"), "events": vol["post30"].get("events")})
    if not assets:
        return None
    return {"type": kind, "assets": assets, "test": data.get("test"),
            "note": "Volatilidade típica medida em 2019-2026, comparada ao mesmo horário em dias sem evento. Não indica direção."}
