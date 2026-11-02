"""Datas de resultados trimestrais (yfinance) e a reação histórica do preço a cada uma."""
from __future__ import annotations

import logging
import time

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_CACHE: dict[str, tuple[float, pd.DataFrame | None]] = {}
TTL_SECONDS = 6 * 3600


def earnings_table(symbol: str) -> pd.DataFrame | None:
    """Índice = data/hora do resultado (sem fuso); colunas do yfinance. None se indisponível."""
    hit = _CACHE.get(symbol)
    if hit and time.time() - hit[0] < TTL_SECONDS:
        return hit[1]
    table = None
    try:
        import yfinance as yf

        raw = yf.Ticker(symbol).get_earnings_dates(limit=40)
        if raw is not None and len(raw):
            table = raw.copy()
            idx = pd.DatetimeIndex(table.index)
            table.index = idx.tz_localize(None) if idx.tz is not None else idx
    except Exception:
        logger.warning("Sem datas de resultado para %s (yfinance/lxml indisponível)", symbol)
    _CACHE[symbol] = (time.time(), table)
    return table


def next_earnings(table: pd.DataFrame | None, today: pd.Timestamp) -> pd.Timestamp | None:
    if table is None or table.empty:
        return None
    future = table.index[table.index.normalize() >= today.normalize()]
    return future.min() if len(future) else None


def reactions(history: pd.DataFrame, table: pd.DataFrame | None) -> pd.Series:
    """Variação (fração) do fechamento no dia em que o mercado reagiu a cada resultado já divulgado."""
    if table is None or table.empty or history.empty or "Reported EPS" not in table:
        return pd.Series(dtype=float)
    out = {}
    close = history["close"]
    for ts in table.index[table["Reported EPS"].notna()]:
        day = ts.normalize()
        pos = history.index.searchsorted(day)
        if pos >= len(history) or pos < 1:
            continue
        if ts.hour >= 15 and history.index[pos] == day:  # depois do fechamento: reação no dia seguinte
            pos += 1
        if pos >= len(history) or history.index[pos] < day:
            continue
        out[history.index[pos]] = close.iloc[pos] / close.iloc[pos - 1] - 1
    return pd.Series(out, dtype=float).sort_index()
