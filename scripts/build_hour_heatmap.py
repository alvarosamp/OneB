"""Mapa de horários: volatilidade e custo por dia da semana e hora, medidos no M5 da Dukascopy.

    python scripts/build_hour_heatmap.py

Período: os 2 anos mais recentes do arquivo (regime atual). Hora de Nova York, que é onde
abertura e fechamento dos EUA ficam fixos o ano todo (o horário de verão muda a hora em
Brasília, não em NY). Grava app/research_results/hour_heatmap.json (pequeno, versionado:
produção não tem o HD externo).

Por célula (dia útil x hora de NY):
- range_bps: mediana da amplitude da hora (máxima - mínima) em pontos-base do preço;
- ratio: range_bps / mediana de todas as horas do ativo (1,0 = hora típica);
- spread_bps: mediana do spread na hora (Dukascopy) e, quando houver, o da HonorPro;
- cost_share: custo de ida e volta na corretora / amplitude típica da hora (quanto do
  movimento da hora o spread come).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.lab.data import DUKASCOPY_FILES, HONOR_UTC_OFFSET_HOURS, honor_hourly_spread  # noqa: E402

ASSETS = {"NAS100": ("Nasdaq 100", "US100.s"), "SPX500": ("S&P 500", "US500.s"),
          "XAUUSD": ("Ouro", "XAUUSD.s"), "EURUSD": ("Euro/dólar", None)}
YEARS = 2
MIN_HOURS = 20  # célula com menos horas de amostra fica vazia


def hourly(asset: str) -> pd.DataFrame:
    raw = pd.read_csv(DUKASCOPY_FILES[asset], usecols=["timestamp", "bid_high", "bid_low", "bid_close", "spread_open"])
    ts = pd.to_datetime(raw["timestamp"], utc=True)
    raw.index = ts
    end = ts.max()
    raw = raw[raw.index >= end - pd.DateOffset(years=YEARS)]
    g = raw.resample("1h")
    h = pd.DataFrame({"high": g["bid_high"].max(), "low": g["bid_low"].min(), "close": g["bid_close"].last(),
                      "spread": g["spread_open"].median(), "bars": g["bid_close"].count()}).dropna()
    h = h[(h["bars"] >= 10) & (h["high"] > h["low"])]  # hora com negociação de verdade
    ny = h.index.tz_convert("America/New_York")
    h["weekday"], h["hour"] = ny.weekday, ny.hour
    h["utc_hour"] = h.index.hour
    h["range_bps"] = (h["high"] - h["low"]) / h["close"] * 1e4
    h["spread_bps"] = h["spread"] / h["close"] * 1e4
    return h[h["weekday"] < 5]


def main() -> None:
    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "timezone": "America/New_York",
           "method": __doc__.split("Por célula")[0].strip(), "assets": {}}
    for asset, (label, honor_symbol) in ASSETS.items():
        h = hourly(asset)
        honor = honor_hourly_spread(asset)  # preço, por hora UTC (abr-set/2026)
        if honor:
            h["honor_bps"] = h["utc_hour"].map(lambda u: honor.get(int(u), np.nan)) / h["close"] * 1e4
        typical = float(h["range_bps"].median())
        cells = []
        for (wd, hr), g in h.groupby(["weekday", "hour"]):
            if len(g) < MIN_HOURS:
                continue
            rng = float(g["range_bps"].median())
            spread = float(g["spread_bps"].median())
            broker = float(g["honor_bps"].median()) if honor and g["honor_bps"].notna().any() else None
            cost = broker if broker is not None else spread
            cells.append({"weekday": int(wd), "hour": int(hr), "range_bps": round(rng, 2), "ratio": round(rng / typical, 2),
                          "spread_bps": round(spread, 3), "broker_spread_bps": round(broker, 3) if broker is not None else None,
                          "cost_share": round(cost / rng, 4), "hours": int(len(g))})
        out["assets"][asset] = {
            "label": label, "broker_symbol": honor_symbol if honor else None,
            "period": {"from": h.index.min().date().isoformat(), "to": h.index.max().date().isoformat()},
            "typical_range_bps": round(typical, 2), "cells": cells,
            "cost_source": "HonorPro (spread medido abr-set/2026)" if honor else "Dukascopy (sem símbolo na HonorPro)",
        }
        best = sorted(cells, key=lambda c: c["cost_share"])[:3]
        print(asset, label, "típica", round(typical, 1), "bps |", len(cells), "células | menor custo relativo:",
              [(c["weekday"], c["hour"], c["cost_share"]) for c in best], flush=True)
    path = ROOT / "app" / "research_results" / "hour_heatmap.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(path, f"{path.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    _ = HONOR_UTC_OFFSET_HOURS
    main()
