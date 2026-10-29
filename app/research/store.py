"""Histórico diário em disco (CSV por ativo), para formar séries longas sem depender da API.

O yfinance só devolve janelas limitadas; ao acumular localmente a cada atualização, o
histórico passa a crescer e as análises ganham amostra. `data/` já está no .gitignore.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_DIR = Path("data/history")
_COLUMNS = ["open", "high", "low", "close", "volume"]

Fetcher = Callable[[str, str, str], pd.DataFrame]


def _path(symbol: str, directory: Path) -> Path:
    safe = re.sub(r"[^A-Za-z0-9]+", "_", symbol).strip("_") or "symbol"
    return directory / f"{safe}.csv"


def load(symbol: str, directory: Path = DEFAULT_DIR) -> pd.DataFrame:
    path = _path(symbol, directory)
    if not path.exists():
        return pd.DataFrame(columns=_COLUMNS)
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df[_COLUMNS].sort_index()


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df[_COLUMNS].copy()
    idx = pd.DatetimeIndex(out.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    out.index = idx.normalize()  # barras diárias: uma por dia
    out.index.name = "timestamp"
    return out


def update(
    symbol: str,
    directory: Path = DEFAULT_DIR,
    fetcher: Fetcher | None = None,
    initial_period: str = "5y",
    refresh_period: str = "1mo",
) -> pd.DataFrame:
    """Busca dados novos, mescla com o que já existe e grava. Falha de rede mantém o local."""
    if fetcher is None:
        from app.market_data.yfinance_client import get_history

        fetcher = get_history

    existing = load(symbol, directory)
    period = refresh_period if not existing.empty else initial_period
    fresh = fetcher(symbol, period, "1d")
    if fresh is None or fresh.empty:
        logger.warning("Sem dados novos para %s; mantendo histórico local", symbol)
        return existing

    merged = pd.concat([existing, _normalize(fresh)])
    merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    directory.mkdir(parents=True, exist_ok=True)
    merged.to_csv(_path(symbol, directory))
    return merged


def load_closes(symbols: list[str], directory: Path = DEFAULT_DIR) -> pd.DataFrame:
    """Matriz de fechamentos (colunas = ativos), alinhada por data. Ativos sem dados são omitidos."""
    cols = {}
    for symbol in symbols:
        df = load(symbol, directory)
        if not df.empty:
            cols[symbol] = df["close"]
    return pd.DataFrame(cols).sort_index()
