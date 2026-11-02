"""Registro em tempo real (paper trading) do estado de tendência por ativo.

Regra acompanhada: posicionado quando o regime de tendência é de alta (preço e SMA50 acima da SMA200),
fora caso contrário. É o modelo de redução de risco da pesquisa, não uma previsão de preço. O arquivo só
cresce: cada (data, ativo) é gravado uma vez, no momento em que a barra fecha, e nunca é reescrito. Assim o
histórico pode ser auditado depois, ao contrário de um backtest.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import regimes

DEFAULT_PATH = Path("data/signals/log.csv")
COLUMNS = ["date", "symbol", "state", "close", "trend", "logged_at"]
COST = 0.0010  # por lado, igual ao restante da pesquisa


def load(path: Path = DEFAULT_PATH) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame(columns=COLUMNS)


def record(histories: dict[str, pd.DataFrame], path: Path = DEFAULT_PATH) -> dict:
    """Acrescenta o estado da última barra de cada ativo. Datas já registradas são ignoradas."""
    log = load(path)
    seen = set(zip(log["date"], log["symbol"]))
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for symbol, hist in histories.items():
        close = hist["close"].dropna() if hist is not None and not hist.empty else pd.Series(dtype=float)
        if len(close) < 220:
            continue
        trend = regimes.regime_summary(close)["trend"]
        day = close.index[-1].date().isoformat()
        if (day, symbol) in seen or trend is None:
            continue
        rows.append(
            {"date": day, "symbol": symbol, "state": int(trend == "up"), "close": round(float(close.iloc[-1]), 4),
             "trend": trend, "logged_at": now}
        )
    if rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        out = pd.concat([log, pd.DataFrame(rows, columns=COLUMNS)], ignore_index=True)
        out.to_csv(path, index=False)
    return {"new": len(rows), "total": len(log) + len(rows)}


def evaluate(log: pd.DataFrame, histories: dict[str, pd.DataFrame]) -> dict:
    """Retorno do estado registrado (execução na abertura seguinte) contra comprar e segurar no mesmo período."""
    per_symbol, series_s, series_b = [], [], []
    for symbol, g in log.groupby("symbol"):
        hist = histories.get(symbol)
        if hist is None or hist.empty:
            continue
        g = g.assign(date=pd.to_datetime(g["date"])).sort_values("date").drop_duplicates("date")
        opens = hist["open"]
        pos = opens.index.get_indexer(g["date"]) + 1  # sinal no fechamento de d, execução na abertura de d+1
        pos = np.where(pos > 0, pos, -1)
        valid = (pos >= 0) & (pos + 1 < len(opens))
        if not valid.any():
            continue
        entry = opens.iloc[pos[valid]].values
        exit_ = opens.iloc[pos[valid] + 1].values
        bh = exit_ / entry - 1
        state = g["state"].values[valid].astype(float)
        turn = np.abs(np.diff(np.concatenate([[0.0], state])))  # custo ao mudar de posição
        strat = state * bh - turn * COST
        idx = g["date"].values[valid]
        series_s.append(pd.Series(strat, index=idx))
        series_b.append(pd.Series(bh, index=idx))
        per_symbol.append(
            {
                "symbol": symbol,
                "days": int(valid.sum()),
                "days_in_position": int(state.sum()),
                "strategy_pct": round(float(np.prod(1 + strat) - 1) * 100, 2),
                "buy_hold_pct": round(float(np.prod(1 + bh) - 1) * 100, 2),
            }
        )
    out = {"symbols": sorted(per_symbol, key=lambda r: r["symbol"]), "aggregate": None}
    if series_s:
        s = pd.concat(series_s, axis=1).mean(axis=1)
        b = pd.concat(series_b, axis=1).mean(axis=1)
        out["aggregate"] = {
            "days": int(len(s)),
            "strategy_pct": round(float(np.prod(1 + s) - 1) * 100, 2),
            "buy_hold_pct": round(float(np.prod(1 + b) - 1) * 100, 2),
            "worst_day_strategy_pct": round(float(s.min()) * 100, 2),
            "worst_day_buy_hold_pct": round(float(b.min()) * 100, 2),
        }
    return out
