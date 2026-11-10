import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from tests.helpers import install_test_user
from app.db import Base, get_db
from app.main import app
from app.models import AlertLog, GlobalNewsItem, PriceSnapshot, Transaction, TransactionSide, WatchlistItem
from app.market_data.yfinance_client import CommodityQuote, FxQuote
import pandas as pd


@pytest.fixture()
def client():
    # StaticPool keeps a single shared connection alive so every session sees
    # the same in-memory sqlite database (plain :memory: gives each new
    # connection its own empty database).
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    TestingSession.user_id = install_test_user(app, TestingSession)

    # Deliberately NOT using TestClient as a context manager: that would trigger
    # app.main's lifespan (real DB init, real scheduler, real Telegram polling
    # using whatever is in .env) which we don't want running during unit tests.
    test_client = TestClient(app)
    yield test_client, TestingSession

    app.dependency_overrides.clear()


def test_dashboard_summary_empty(client):
    test_client, _ = client
    res = test_client.get("/api/dashboard-summary")
    assert res.status_code == 200
    assert res.json() == {"rows": [], "alerts": []}


def test_dashboard_summary_with_data(client):
    test_client, Session = client
    db = Session()
    item = WatchlistItem(user_id=Session.user_id, symbol="AAPL", label="Apple")
    db.add(item)
    db.commit()
    db.add(PriceSnapshot(watchlist_item_id=item.id, price=150.5, change_pct=1.2, volume=1000))
    db.commit()
    db.close()

    res = test_client.get("/api/dashboard-summary")
    assert res.status_code == 200
    data = res.json()
    assert len(data["rows"]) == 1
    assert data["rows"][0]["symbol"] == "AAPL"
    assert data["rows"][0]["price"] == 150.5


def test_alerts_filter_by_symbol(client):
    test_client, Session = client
    db = Session()
    db.add(AlertLog(user_id=Session.user_id, symbol="AAPL", rule_type="PRICE_ABOVE", message="AAPL subiu"))
    db.add(AlertLog(user_id=Session.user_id, symbol="MSFT", rule_type="PRICE_ABOVE", message="MSFT subiu"))
    db.commit()
    db.close()

    res = test_client.get("/api/alerts", params={"symbol": "aapl"})
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "AAPL"


def test_alerts_filter_by_rule_type(client):
    test_client, Session = client
    db = Session()
    db.add(AlertLog(user_id=Session.user_id, symbol="AAPL", rule_type="PRICE_ABOVE", message="a"))
    db.add(AlertLog(user_id=Session.user_id, symbol="AAPL", rule_type="RSI_OVERBOUGHT", message="b"))
    db.commit()
    db.close()

    res = test_client.get("/api/alerts", params={"rule_type": "RSI_OVERBOUGHT"})
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["rule_type"] == "RSI_OVERBOUGHT"


def test_alerts_no_filter_returns_all(client):
    test_client, Session = client
    db = Session()
    db.add(AlertLog(user_id=Session.user_id, symbol="AAPL", rule_type="PRICE_ABOVE", message="a"))
    db.add(AlertLog(user_id=Session.user_id, symbol="MSFT", rule_type="PRICE_ABOVE", message="b"))
    db.commit()
    db.close()

    res = test_client.get("/api/alerts")
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_news_endpoint_empty(client):
    test_client, _ = client
    res = test_client.get("/api/news")
    assert res.status_code == 200
    assert res.json() == []


def test_usd_brl_quote_endpoint(client, monkeypatch):
    test_client, _ = client

    def fake_quote():
        return FxQuote(
            pair="USD/BRL",
            rate=5.4321,
            change_pct=0.75,
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    monkeypatch.setattr("app.routers.api.yfinance_client.get_usd_brl_quote", fake_quote)

    res = test_client.get("/api/fx/usd-brl")
    assert res.status_code == 200
    assert res.json()["rate"] == 5.4321
    assert res.json()["change_pct"] == 0.75


def test_gold_quote_endpoint(client, monkeypatch):
    test_client, _ = client

    def fake_quote():
        return CommodityQuote(
            symbol="GC=F",
            name="Ouro",
            unit="onca troy",
            price=2400.55,
            change_pct=-0.25,
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    monkeypatch.setattr("app.routers.api.yfinance_client.get_gold_quote", fake_quote)

    res = test_client.get("/api/commodities/gold")
    assert res.status_code == 200
    assert res.json()["symbol"] == "GC=F"
    assert res.json()["price"] == 2400.55
    assert res.json()["change_pct"] == -0.25


def test_global_news_endpoint_orders_by_impact(client):
    test_client, Session = client
    db = Session()
    db.add(
        GlobalNewsItem(
            category="general",
            headline="Fed signals rate decision",
            url="https://example.com/fed",
            source="Example",
            impact_score=60,
            published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )
    db.add(
        GlobalNewsItem(
            category="general",
            headline="Minor market update",
            url="https://example.com/minor",
            source="Example",
            impact_score=5,
            published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )
    db.commit()
    db.close()

    res = test_client.get("/api/global-news")
    assert res.status_code == 200
    data = res.json()
    assert [item["headline"] for item in data] == ["Fed signals rate decision", "Minor market update"]


def test_global_news_endpoint_filters_by_min_impact(client):
    test_client, Session = client
    db = Session()
    db.add(
        GlobalNewsItem(
            category="general",
            headline="Fed signals rate decision",
            url="https://example.com/fed",
            source="Example",
            impact_score=60,
            published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )
    db.add(
        GlobalNewsItem(
            category="general",
            headline="Minor market update",
            url="https://example.com/minor",
            source="Example",
            impact_score=5,
            published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )
    db.commit()
    db.close()

    res = test_client.get("/api/global-news", params={"min_impact": 40})
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["impact_score"] == 60


def test_copilot_analyze_endpoint(client, monkeypatch):
    test_client, Session = client
    db = Session()
    item = WatchlistItem(user_id=Session.user_id, symbol="NVDA", label="Nvidia")
    db.add(item)
    db.commit()
    db.add(PriceSnapshot(watchlist_item_id=item.id, price=120.0, change_pct=1.5, volume=1000))
    db.commit()
    db.close()

    dates = pd.date_range("2026-01-01", periods=80, freq="D", tz="UTC")
    history = pd.DataFrame(
        {
            "open": [100 + i * 0.2 for i in range(80)],
            "high": [101 + i * 0.2 for i in range(80)],
            "low": [99 + i * 0.2 for i in range(80)],
            "close": [100 + i * 0.2 for i in range(80)],
            "volume": [1000 + i for i in range(80)],
        },
        index=dates,
    )

    monkeypatch.setattr("app.copilot.yfinance_client.get_history", lambda *args, **kwargs: history)

    res = test_client.post(
        "/api/copilot/analyze",
        json={"symbol": "NVDA", "capital_usd": 20000, "risk_budget_pct": 1, "question": "vale olhar?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["symbol"] == "NVDA"
    assert "votes" in data
    assert len(data["votes"]) == 5
    assert "simulation" in data


def test_trader_profile_endpoint_with_closed_trade(client):
    test_client, Session = client
    db = Session()
    db.add(
        Transaction(user_id=Session.user_id, 
            symbol="NVDA",
            side=TransactionSide.BUY,
            quantity=10,
            price=100,
            executed_at=datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
        )
    )
    db.add(
        Transaction(user_id=Session.user_id, 
            symbol="NVDA",
            side=TransactionSide.SELL,
            quantity=10,
            price=110,
            executed_at=datetime(2026, 1, 2, 10, tzinfo=timezone.utc),
        )
    )
    db.commit()
    db.close()

    res = test_client.get("/api/profile/trader")
    assert res.status_code == 200
    data = res.json()
    assert data["summary"]["closed_trades"] == 1
    assert data["summary"]["total_pnl"] == 100
    assert data["journal"][0]["return_pct"] == 10


def test_morning_report_today_404_when_none_generated(client):
    test_client, _ = client
    res = test_client.get("/api/morning-report/today")
    assert res.status_code == 404


def test_morning_report_generate_and_fetch(client, monkeypatch):
    test_client, _ = client
    monkeypatch.setattr("app.morning_report.yfinance_client.get_nasdaq_quote", lambda: None)
    monkeypatch.setattr("app.morning_report.yfinance_client.get_sp500_quote", lambda: None)
    monkeypatch.setattr("app.morning_report.yfinance_client.get_gold_quote", lambda: None)
    monkeypatch.setattr("app.morning_report.settings.llm_daily_narrative_enabled", False)

    res = test_client.post("/api/morning-report/generate")
    assert res.status_code == 200
    generated = res.json()
    assert generated["data"]["indices"] == []
    assert generated["narrative"]

    today_res = test_client.get("/api/morning-report/today")
    assert today_res.status_code == 200
    assert today_res.json()["id"] == generated["id"]

    history_res = test_client.get("/api/morning-report/history")
    assert history_res.status_code == 200
    assert len(history_res.json()) == 1

    pdf_res = test_client.get(f"/api/morning-report/{generated['id']}/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.content.startswith(b"%PDF")


def test_morning_report_pdf_404_for_unknown_id(client):
    test_client, _ = client
    res = test_client.get("/api/morning-report/999/pdf")
    assert res.status_code == 404
