"""Probabilidades medidas dos planos de trade (stop e alvos por ATR), para a 'confiança' do produto.

    python scripts/build_trade_plan_rates.py

Não é um teste de estratégia: é a TAXA-BASE de cada plano. Para cada hora cheia de 2023-01 a
2026-09 (e 2019-2022 como comparação), entra comprado e vendido na abertura da barra M5
(compra no ask, venda no bid) e acompanha por até 24 h:
- stop = s x ATR(14) do H1 já fechado, s em {1,0; 1,5; 2,0}
- alvos = 1R, 2R e 3R; stop e alvo na mesma barra contam como stop (conservador)
- sem stop nem alvo em 24 h: sai no fechamento (resultado em R)
Grava app/research_results/trade_plan_rates.json com taxas por ativo, direção, plano e hora de NY.
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

from app.lab.data import DUKASCOPY_FILES  # noqa: E402

ASSETS = ["NAS100", "XAUUSD", "SPX500", "EURUSD"]
STOPS = [1.0, 1.5, 2.0]
TARGETS = [1.0, 2.0, 3.0]
HORIZON = 288  # barras M5 = 24 h
PERIODS = {"recent": ("2023-01-01", "2026-09-26"), "older": ("2019-03-01", "2023-01-01")}


def load(asset: str) -> pd.DataFrame:
    cols = ["timestamp", "bid_open", "bid_high", "bid_low", "bid_close", "ask_open", "ask_high", "ask_low", "ask_close"]
    d = pd.read_csv(DUKASCOPY_FILES[asset], usecols=cols)
    d.index = pd.to_datetime(d["timestamp"], utc=True)
    return d.drop(columns="timestamp").sort_index()


def h1_atr(m5: pd.DataFrame) -> pd.Series:
    """ATR(14) do H1 conhecido no fim de cada hora, indexado pelo instante em que fica disponível."""
    h = m5.resample("1h").agg({"bid_high": "max", "bid_low": "min", "bid_close": "last"}).dropna()
    prev = h["bid_close"].shift()
    tr = pd.concat([h["bid_high"] - h["bid_low"], (h["bid_high"] - prev).abs(), (h["bid_low"] - prev).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    atr.index = atr.index + pd.Timedelta(hours=1)
    return atr.dropna()


def simulate(m5: pd.DataFrame, lo: str, hi: str) -> list[dict]:
    atr = h1_atr(m5)
    idx = m5.index
    entries = np.where((idx.minute == 0) & (idx >= pd.Timestamp(lo, tz="UTC")) & (idx < pd.Timestamp(hi, tz="UTC")))[0]
    entries = entries[entries + HORIZON < len(idx)]
    # ATR disponível no instante da entrada
    a = atr.reindex(idx[entries], method="ffill").to_numpy()
    ok = np.isfinite(a) & (a > 0)
    entries, a = entries[ok], a[ok]
    # janela de 24 h contínua no tempo (descarta entradas cuja janela atravessa buracos grandes)
    span = (idx[entries + HORIZON] - idx[entries]).total_seconds() / 3600
    keep = span <= 72  # fins de semana cabem; buracos de dados não
    entries, a = entries[keep], a[keep]
    hours_ny = idx[entries].tz_convert("America/New_York").hour.to_numpy()
    arr = {k: m5[k].to_numpy() for k in m5.columns}
    rows = []
    for direction in ("long", "short"):
        entry = arr["ask_open"][entries] if direction == "long" else arr["bid_open"][entries]
        for s in STOPS:
            stop_dist = s * a
            for t in TARGETS:
                outcome = np.zeros(len(entries))  # 1 = alvo, -1 = stop, 0 = nenhum
                result_r = np.full(len(entries), np.nan)
                open_ = np.ones(len(entries), dtype=bool)
                for step in range(HORIZON):
                    j = entries + step
                    if direction == "long":
                        hit_stop = arr["bid_low"][j] <= entry - stop_dist
                        hit_tp = arr["bid_high"][j] >= entry + t * stop_dist
                    else:
                        hit_stop = arr["ask_high"][j] >= entry + stop_dist
                        hit_tp = arr["ask_low"][j] <= entry - t * stop_dist
                    stop_now = open_ & hit_stop
                    tp_now = open_ & hit_tp & ~hit_stop
                    outcome[stop_now], result_r[stop_now] = -1, -1.0
                    outcome[tp_now], result_r[tp_now] = 1, t
                    open_ &= ~(stop_now | tp_now)
                    if not open_.any():
                        break
                last = entries + HORIZON
                exit_px = arr["bid_close"][last] if direction == "long" else arr["ask_close"][last]
                pnl = (exit_px - entry) if direction == "long" else (entry - exit_px)
                result_r[open_] = (pnl / stop_dist)[open_]
                for hour in [None, *range(24)]:
                    m = np.ones(len(entries), dtype=bool) if hour is None else hours_ny == hour
                    n = int(m.sum())
                    if n < 30:
                        continue
                    rows.append({"direction": direction, "stop_atr": s, "target_r": t, "ny_hour": hour, "n": n,
                                 "p_target": round(float((outcome[m] == 1).mean()), 4), "p_stop": round(float((outcome[m] == -1).mean()), 4),
                                 "p_open_24h": round(float((outcome[m] == 0).mean()), 4), "mean_r": round(float(np.nanmean(result_r[m])), 4)})
    return rows


def main() -> None:
    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "method": __doc__.strip(), "assets": {}}
    for asset in ASSETS:
        m5 = load(asset)
        out["assets"][asset] = {}
        for name, (lo, hi) in PERIODS.items():
            rows = simulate(m5, lo, hi)
            out["assets"][asset][name] = rows
            allh = [r for r in rows if r["ny_hour"] is None and r["stop_atr"] == 1.5]
            print(asset, name, [(r["direction"], r["target_r"], r["n"], r["p_target"], r["mean_r"]) for r in allh], flush=True)
    path = ROOT / "app" / "research_results" / "trade_plan_rates.json"
    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(path, f"{path.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
