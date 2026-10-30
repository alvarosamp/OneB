"""Arquivo local de manchetes, para formar o histórico que as APIs gratuitas não oferecem.

Cada coleta junta as manchetes atuais (RSS/Finnhub) num único CSV, sem duplicar. Com meses de
acúmulo dá para testar se o sentimento das manchetes antecede o preço, com a mesma metodologia
de `scripts/research_*.py`.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_DIR = Path("data/news")
ARCHIVE_NAME = "archive.csv"
COLUMNS = ["collected_at", "symbol", "published_at", "source", "headline", "url"]
MARKET = "MARKET"

Fetcher = Callable[[str], list]


def _default_fetchers() -> tuple[Fetcher, Fetcher]:
    from app.market_data import rss_news

    return (lambda s: rss_news.get_company_news(s, limit=20), lambda _: rss_news.get_market_news("general", limit=30))


def load(directory: Path = DEFAULT_DIR) -> pd.DataFrame:
    path = directory / ARCHIVE_NAME
    if path.exists():
        return pd.read_csv(path)
    # semeia com coletas antigas (um CSV por dia, sem coluna de url)
    legacy = [pd.read_csv(p) for p in sorted(directory.glob("20*.csv"))] if directory.exists() else []
    if not legacy:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.concat(legacy)
    df["collected_at"] = df.get("collected_at", datetime.now(timezone.utc).isoformat())
    df["url"] = df.get("url", "")
    return df[COLUMNS]


def collect(
    symbols: list[str],
    directory: Path = DEFAULT_DIR,
    company_fetcher: Fetcher | None = None,
    market_fetcher: Fetcher | None = None,
) -> dict:
    """Busca manchetes de cada ativo + mercado geral e acrescenta as novas ao arquivo."""
    if company_fetcher is None or market_fetcher is None:
        dc, dm = _default_fetchers()
        company_fetcher, market_fetcher = company_fetcher or dc, market_fetcher or dm

    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for symbol in [MARKET, *symbols]:
        fetch = market_fetcher if symbol == MARKET else company_fetcher
        try:
            articles = fetch(symbol)
        except Exception:
            logger.exception("Falha ao coletar manchetes de %s", symbol)
            continue
        for a in articles:
            rows.append(
                {
                    "collected_at": now,
                    "symbol": symbol,
                    "published_at": a.published_at.isoformat(),
                    "source": a.source,
                    "headline": a.headline,
                    "url": a.url,
                }
            )

    existing = load(directory)
    before = len(existing)
    merged = pd.concat([existing, pd.DataFrame(rows, columns=COLUMNS)], ignore_index=True)
    merged = merged.drop_duplicates(["symbol", "headline"], keep="first")
    directory.mkdir(parents=True, exist_ok=True)
    merged.to_csv(directory / ARCHIVE_NAME, index=False)
    return {"fetched": len(rows), "new": len(merged) - before, "total": len(merged), "symbols": len(symbols)}


def research_symbols(history_dir: Path = Path("data/history")) -> list[str]:
    """Tickers com histórico de preços salvo (ignora futuros/câmbio como GC_F, BRL_X)."""
    if not history_dir.exists():
        return []
    return sorted(p.stem for p in history_dir.glob("*.csv") if re.fullmatch(r"[A-Z]{1,5}", p.stem))
