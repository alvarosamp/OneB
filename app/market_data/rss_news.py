"""Notícias via RSS público (sem API key).

Fallback do Finnhub: sem FINNHUB_API_KEY (ou quando o free tier devolve vazio) o painel de
mercado ficava sem nenhuma notícia. Yahoo Finance (por ativo) e CNBC (mercado geral) publicam
RSS aberto, então o app sempre tem manchetes reais mesmo sem configurar chave.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape

import httpx

from app.market_data.finnhub_client import NewsArticle

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NasdaqMonitor/1.0)"}
_YAHOO_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
_CNBC_URL = "https://www.cnbc.com/id/{feed_id}/device/rss/rss.html"

# categoria interna (settings.global_news_categories) -> feeds da CNBC
_CNBC_FEEDS: dict[str, list[tuple[str, str]]] = {
    "general": [("100003114", "CNBC Top News"), ("10000664", "CNBC Finance")],
    "forex": [("20910258", "CNBC Economy")],
    "economy": [("20910258", "CNBC Economy")],
    "investing": [("15839069", "CNBC Investing")],
}

_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str | None) -> str:
    return unescape(_TAG_RE.sub("", text or "")).strip()


def _parse_date(raw: str | None) -> datetime:
    try:
        parsed = parsedate_to_datetime(raw) if raw else None
    except (TypeError, ValueError):
        parsed = None
    if parsed is None:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _fetch_items(url: str) -> list[ET.Element]:
    try:
        resp = httpx.get(url, headers=_HEADERS, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        return ET.fromstring(resp.content).findall("./channel/item")
    except Exception:
        logger.exception("Falha ao ler RSS %s", url)
        return []


def _to_articles(items: list[ET.Element], symbol: str, default_source: str, limit: int) -> list[NewsArticle]:
    articles = []
    for item in items[:limit]:
        headline = _clean(item.findtext("title"))
        url = (item.findtext("link") or "").strip()
        if not headline or not url:
            continue
        articles.append(
            NewsArticle(
                symbol=symbol,
                headline=headline,
                summary=_clean(item.findtext("description")),
                url=url,
                source=default_source,
                published_at=_parse_date(item.findtext("pubDate")),
            )
        )
    return articles


def get_company_news(symbol: str, limit: int = 20) -> list[NewsArticle]:
    items = _fetch_items(_YAHOO_URL.format(symbol=symbol))
    return _to_articles(items, symbol, "Yahoo Finance", limit)


def get_market_news(category: str = "general", limit: int = 30) -> list[NewsArticle]:
    feeds = _CNBC_FEEDS.get(category.lower(), _CNBC_FEEDS["general"])
    articles: list[NewsArticle] = []
    for feed_id, source in feeds:
        items = _fetch_items(_CNBC_URL.format(feed_id=feed_id))
        articles.extend(_to_articles(items, category.upper(), source, limit))
    return articles[:limit]
