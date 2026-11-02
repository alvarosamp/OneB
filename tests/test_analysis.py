import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import analysis
from app.db import Base
from app.market_data import rss_news
from app.models import GlobalNewsItem, WatchlistItem, utcnow


def _history(n: int = 120) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=n, freq="D")
    close = pd.Series(np.linspace(100, 160, n) + np.sin(np.arange(n)), index=idx)
    return pd.DataFrame(
        {"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1_000_000.0}, index=idx
    )


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_technical_snapshot_has_concrete_numbers():
    snap = analysis.technical_snapshot("AAPL", history=_history())
    assert snap["price"] is not None
    assert snap["rsi14"] is not None
    assert snap["s1"] < snap["pivot"] < snap["r1"]
    assert snap["notes"]


def test_technical_snapshot_empty_history():
    assert analysis.technical_snapshot("AAPL", history=pd.DataFrame()) is None


def test_export_csv_contains_sections_and_news(monkeypatch):
    monkeypatch.setattr(analysis.yfinance_client, "get_history", lambda *a, **kw: _history())
    db = _session()
    db.add(WatchlistItem(symbol="AAPL", label="Apple"))
    db.add(
        GlobalNewsItem(
            category="general", headline="Fed holds rates", summary="", url="http://x/1",
            source="CNBC", impact_score=54, published_at=utcnow(),
        )
    )
    db.commit()

    data = analysis.build_export(db)
    assert data["analysis"][0]["symbol"] == "AAPL"
    assert data["global_news"][0]["headline"] == "Fed holds rates"
    csv_text = analysis.export_csv(data)
    assert "# Análise técnica" in csv_text
    assert "Fed holds rates" in csv_text


RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Apple &amp; friends rally</title><link>http://a/1</link>
<description>&lt;p&gt;Body&lt;/p&gt;</description><pubDate>Thu, 29 Oct 2026 16:25:40 GMT</pubDate></item>
<item><title></title><link>http://a/2</link></item>
</channel></rss>"""


def test_rss_parsing(monkeypatch):
    class Resp:
        content = RSS

        def raise_for_status(self):
            pass

    monkeypatch.setattr(rss_news.httpx, "get", lambda *a, **kw: Resp())
    articles = rss_news.get_company_news("AAPL")
    assert len(articles) == 1
    assert articles[0].headline == "Apple & friends rally"
    assert articles[0].summary == "Body"
    assert articles[0].published_at.year == 2026


def test_rss_failure_returns_empty(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("network")

    monkeypatch.setattr(rss_news.httpx, "get", boom)
    assert rss_news.get_market_news("general") == []
