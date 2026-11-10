import asyncio
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import morning_report
from app.db import Base
from app.market_data.yfinance_client import IndexQuote
from app.models import GlobalNewsItem, PriceSnapshot, WatchlistItem


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _daily_history(n=30, base=100.0):
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {
            "open": [base] * n,
            "high": [base + 2] * n,
            "low": [base - 2] * n,
            "close": [base] * n,
            "volume": [1000] * n,
        },
        index=idx,
    )


def test_build_report_data_includes_indices_and_watchlist(monkeypatch):
    db = _make_session()
    item = WatchlistItem(symbol="AAPL", label="Apple")
    db.add(item)
    db.commit()
    db.add(PriceSnapshot(watchlist_item_id=item.id, price=150.0, change_pct=1.2, volume=1000))
    db.add(
        GlobalNewsItem(
            headline="Fed segura juros",
            source="Reuters",
            url="https://example.com/1",
            impact_score=50,
            published_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    fake_quote = IndexQuote(
        symbol="NQ=F",
        name="Nasdaq-100 (futuro)",
        price=18000.0,
        change_pct=0.5,
        day_high=18100.0,
        day_low=17900.0,
        prev_close=17900.0,
        updated_at=datetime.now(timezone.utc),
    )
    monkeypatch.setattr(morning_report.yfinance_client, "get_nasdaq_quote", lambda: fake_quote)
    monkeypatch.setattr(morning_report.yfinance_client, "get_sp500_quote", lambda: None)
    monkeypatch.setattr(morning_report.yfinance_client, "get_gold_quote", lambda: None)
    monkeypatch.setattr(morning_report.market_data_service, "get_bars", lambda *a, **kw: _daily_history())

    data = morning_report.build_report_data(db, user_id=1)

    assert len(data["indices"]) == 1
    assert data["indices"][0]["symbol"] == "NQ=F"
    assert data["indices"][0]["levels"]["pivots"]["pivot"] == 100.0
    assert data["watchlist"] == [
        {"symbol": "AAPL", "price": 150.0, "change_pct": 1.2, "levels": data["watchlist"][0]["levels"]}
    ]
    assert data["overnight_news"][0]["headline"] == "Fed segura juros"


def test_render_text_handles_empty_report():
    data = {
        "date": "2024-01-01",
        "indices": [],
        "watchlist": [],
        "overnight_news": [],
        "economic_events_today": [],
        "earnings_today": [],
    }
    text = morning_report.render_text(data)
    assert "2024-01-01" in text


def test_generate_and_store_persists_report(monkeypatch):
    db = _make_session()
    monkeypatch.setattr(morning_report.yfinance_client, "get_nasdaq_quote", lambda: None)
    monkeypatch.setattr(morning_report.yfinance_client, "get_sp500_quote", lambda: None)
    monkeypatch.setattr(morning_report.yfinance_client, "get_gold_quote", lambda: None)
    monkeypatch.setattr(morning_report.settings, "llm_daily_narrative_enabled", False)

    report = asyncio.run(morning_report.generate_and_store(db, user_id=1))

    assert report.id is not None
    assert report.narrative
    assert report.data["indices"] == []
