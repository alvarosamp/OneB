"""Fontes externas gratuitas: macro/risco (yfinance + FRED sem chave) e revisões de analistas."""
from __future__ import annotations

import io
import logging
from pathlib import Path

import httpx
import pandas as pd

from app.research import store

logger = logging.getLogger(__name__)

MACRO_DIR = Path("data/macro")
ANALYST_DIR = Path("data/analysts")
MACRO_TICKERS = ["^VIX", "^VIX3M", "^VVIX", "DX-Y.NYB", "^TNX", "HYG", "LQD"]
FRED_SERIES = ["T10Y2Y", "NFCI", "DFF"]
_HEADERS = {"User-Agent": "Mozilla/5.0 NasdaqMonitorResearch"}


def update_macro(directory: Path = MACRO_DIR) -> dict:
    ok = {}
    for t in MACRO_TICKERS:
        ok[t] = len(store.update(t, directory, initial_period="12y"))
    for sid in FRED_SERIES:
        try:
            r = httpx.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", headers=_HEADERS, timeout=30, follow_redirects=True)
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text), index_col=0, parse_dates=True)
            df.columns = ["value"]
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            directory.mkdir(parents=True, exist_ok=True)
            df.dropna().to_csv(directory / f"fred_{sid}.csv")
            ok[sid] = len(df)
        except Exception:
            logger.warning("Falha ao baixar FRED %s", sid)
    return ok


def load_fred(sid: str, directory: Path = MACRO_DIR) -> pd.Series:
    df = pd.read_csv(directory / f"fred_{sid}.csv", index_col=0, parse_dates=True)
    return df["value"]


def update_analysts(symbols: list[str], directory: Path = ANALYST_DIR) -> dict:
    import yfinance as yf

    directory.mkdir(parents=True, exist_ok=True)
    out = {}
    for s in symbols:
        try:
            ud = yf.Ticker(s).upgrades_downgrades
            if ud is None or ud.empty:
                continue
            ud = ud.copy()
            ud.index = pd.DatetimeIndex(ud.index).tz_localize(None) if pd.DatetimeIndex(ud.index).tz is not None else pd.DatetimeIndex(ud.index)
            ud.index.name = "date"
            ud.to_csv(directory / f"{s}.csv")
            out[s] = len(ud)
        except Exception:
            logger.warning("Falha em analistas de %s", s)
    return out


def load_analysts(symbol: str, directory: Path = ANALYST_DIR) -> pd.DataFrame:
    p = directory / f"{symbol}.csv"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, index_col=0, parse_dates=True).sort_index()
