import pytest
from datetime import datetime, timezone
from types import SimpleNamespace
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.main import app
from app.market_data.providers import MarketQuote
from app.models import (
    AlertCondition,
    AlertLog,
    AlertRule,
    GlobalNewsItem,
    PriceSnapshot,
    RuleLogic,
    RuleType,
    Transaction,
    TransactionSide,
    WatchlistItem,
)
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
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)

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
    item = WatchlistItem(user_id=1, symbol="AAPL", label="Apple")
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


def test_dashboard_summary_includes_user_item_from_older_workspace(client):
    test_client, Session = client
    db = Session()
    item = WatchlistItem(user_id=1, workspace_id=99, symbol="NVDA", label="Nvidia")
    db.add(item)
    db.commit()
    db.add(PriceSnapshot(watchlist_item_id=item.id, price=120.0, change_pct=1.5, volume=1000))
    db.commit()
    db.close()

    res = test_client.get("/api/dashboard-summary")

    assert res.status_code == 200
    data = res.json()
    assert len(data["rows"]) == 1
    assert data["rows"][0]["symbol"] == "NVDA"


def test_watchlist_delete_allows_user_item_from_older_workspace(client):
    test_client, Session = client
    db = Session()
    item = WatchlistItem(user_id=1, workspace_id=99, symbol="SNAP", label="Snap")
    db.add(item)
    db.commit()
    item_id = item.id
    db.close()

    res = test_client.delete(f"/api/watchlist/{item_id}")

    assert res.status_code == 204
    db = Session()
    assert db.get(WatchlistItem, item_id).active is False
    db.close()


def test_watchlist_rules_allow_user_item_from_older_workspace(client):
    test_client, Session = client
    db = Session()
    item = WatchlistItem(user_id=1, workspace_id=99, symbol="MSFT", label="Microsoft")
    rule = AlertRule(watchlist_item=item, logic=RuleLogic.ALL, cooldown_minutes=30)
    rule.conditions = [AlertCondition(rule_type=RuleType.PRICE_ABOVE, threshold=400)]
    db.add(item)
    db.commit()
    item_id = item.id
    rule_id = rule.id
    db.close()

    list_res = test_client.get(f"/api/watchlist/{item_id}/rules")
    delete_res = test_client.delete(f"/api/watchlist/rules/{rule_id}")

    assert list_res.status_code == 200
    assert list_res.json()[0]["id"] == rule_id
    assert delete_res.status_code == 204
    db = Session()
    assert db.get(AlertRule, rule_id).active is False
    db.close()


def test_watchlist_add_existing_symbol_creates_user_copy(client):
    test_client, Session = client
    db = Session()
    db.add(WatchlistItem(user_id=2, workspace_id=99, symbol="AAPL", label="Other user"))
    db.commit()
    db.close()

    res = test_client.post("/api/watchlist", json={"symbol": "AAPL", "label": "Apple"})

    assert res.status_code == 201
    assert res.json()["symbol"] == "AAPL"
    db = Session()
    rows = db.query(WatchlistItem).filter(WatchlistItem.symbol == "AAPL").order_by(WatchlistItem.id).all()
    assert [(row.user_id, row.workspace_id, row.label) for row in rows] == [(2, 99, "Other user"), (1, 1, "Apple")]
    db.close()


def test_saas_overview_creates_default_workspace(client):
    test_client, _ = client

    res = test_client.get("/api/saas/overview")

    assert res.status_code == 200
    data = res.json()
    assert data["workspace"]["plan"] == "FREE"
    assert data["limits"]["watchlist_items"] == 5
    assert data["usage"]["watchlist_items"] == 0


def test_saas_plan_and_channel_configuration(client):
    test_client, _ = client

    plan_res = test_client.put("/api/saas/plan", json={"plan": "PRO"})
    assert plan_res.status_code == 200
    assert plan_res.json()["workspace"]["plan"] == "PRO"

    channel_res = test_client.post(
        "/api/saas/channels",
        json={"channel_type": "EMAIL", "destination": "alerts@example.com"},
    )
    assert channel_res.status_code == 201
    assert channel_res.json()["destination"] == "alerts@example.com"

    overview = test_client.get("/api/saas/overview").json()
    assert overview["usage"]["notification_channels"] == 1


def test_intelligence_radar_score_and_decision_journal(client):
    test_client, Session = client
    db = Session()
    item = WatchlistItem(symbol="AAPL", label="Apple")
    db.add(item)
    db.commit()
    db.add(PriceSnapshot(watchlist_item_id=item.id, price=190, change_pct=2.5, volume=1000))
    db.commit()
    db.close()

    radar = test_client.get("/api/intelligence/radar")
    assert radar.status_code == 200
    assert radar.json()["scores"][0]["symbol"] == "AAPL"

    score = test_client.get("/api/intelligence/score/AAPL")
    assert score.status_code == 200
    assert score.json()["score"] >= 50

    decision = test_client.post(
        "/api/intelligence/decisions",
        json={"symbol": "AAPL", "thesis": "Rompimento com momentum", "trigger": "Fechar acima da maxima"},
    )
    assert decision.status_code == 201
    assert decision.json()["status"] == "OPEN"

    playbooks = test_client.get("/api/intelligence/playbooks")
    assert playbooks.status_code == 200
    assert len(playbooks.json()) >= 3


def test_intelligence_live_check_uses_market_history(client, monkeypatch):
    test_client, _ = client
    dates = pd.date_range("2026-01-01", periods=5, freq="D", tz="UTC")
    history = pd.DataFrame(
        {
            "open": [100, 101, 102, 103, 104],
            "high": [101, 102, 103, 104, 105],
            "low": [99, 100, 101, 102, 103],
            "close": [100, 102, 101, 104, 106],
            "volume": [1000, 1100, 1200, 1300, 1400],
        },
        index=dates,
    )
    # The endpoint uses the configured market-data provider through the shared
    # service, so patch the service boundary rather than a specific provider.
    # This keeps the test independent from the developer's .env selection.
    monkeypatch.setattr("app.market_data.service.get_bars", lambda *args, **kwargs: history)
    monkeypatch.setattr(
        "app.routers.intelligence.quality_gate",
        lambda *args, **kwargs: {"allowed": True, "confidence": "HIGH", "reason": ""},
    )

    res = test_client.get("/api/intelligence/live-check/AAPL")

    assert res.status_code == 200
    assert "AAPL" in res.json()["score_bot"]


def test_data_quality_compares_multiple_sources(client, monkeypatch):
    test_client, _ = client
    dates = pd.date_range(pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=1), periods=2, freq="D", tz="UTC")
    history = pd.DataFrame(
        {
            "open": [100, 101],
            "high": [101, 102],
            "low": [99, 100],
            "close": [100, 101],
            "volume": [1000, 1100],
        },
        index=dates,
    )

    class FakeQuote:
        price = 101.2
        change_pct = 1.2

    monkeypatch.setattr("app.data_quality.finnhub_client.get_quote", lambda symbol: FakeQuote())
    monkeypatch.setattr(
        "app.data_quality.market_data_service.get_quote",
        lambda symbol, **kwargs: MarketQuote(
            symbol=symbol,
            price=101,
            change_pct=1.0,
            provider="yfinance",
            provider_time=dates[-1].to_pydatetime(),
            received_at=dates[-1].to_pydatetime(),
        ),
    )

    res = test_client.get("/api/intelligence/data-quality/AAPL")

    assert res.status_code == 200
    data = res.json()
    assert data["confidence"] == "HIGH"
    assert len([p for p in data["providers"] if p["available"]]) == 2


def test_free_plan_limits_watchlist_items(client):
    test_client, _ = client

    for symbol in ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]:
        assert test_client.post("/api/watchlist", json={"symbol": symbol}).status_code == 201

    blocked = test_client.post("/api/watchlist", json={"symbol": "META"})

    assert blocked.status_code == 402
    assert "Limite do plano FREE" in blocked.json()["detail"]


def test_operations_health_endpoint(client):
    test_client, _ = client

    res = test_client.get("/api/operations/health")

    assert res.status_code == 200
    data = res.json()
    assert "providers" in data
    assert "data_quality" in data
    assert "db" in data
    assert "market_cache" in data
    assert "paper_simulator" in data
    assert "probability_model" in data
    assert "automation" in data
    assert data["readiness"]["trade_automation_allowed"] is False


def test_operations_lab_endpoint_summarizes_paper_simulator(client, monkeypatch):
    test_client, _ = client

    def fake_read_json(path):
        if path.endswith("paper_simulator_state.json"):
            return {
                "initial_capital": 10000.0,
                "cash": 7500.0,
                "positions": {
                    "AAPL": {
                        "entry_at": "2026-08-10",
                        "entry_price": 200.0,
                        "shares": 5,
                        "stop": 190.0,
                        "target": 220.0,
                        "score": 82,
                    }
                },
                "closed_trades": [],
            }
        if path.endswith("simulation_validation_report.json"):
            return {"can_trade_now": False, "decision_rule": "regra", "risk_rule": "risco", "market_data": []}
        if path.endswith("paper_simulator_deep_replay.json"):
            return {"status": "completed", "return_pct": 3.2, "win_rate_pct": 55.0}
        if path.endswith("automation_readiness_report.json"):
            return {"verdict": "HUMAN_APPROVAL_REQUIRED", "recommendation": "manter humano"}
        return None

    monkeypatch.setattr("app.routers.operations._read_json", fake_read_json)
    monkeypatch.setattr(
        "app.routers.operations._read_jsonl_tail",
        lambda *args, **kwargs: [
            {"at": "2026-08-10T10:00:00+00:00", "type": "calibration", "calibration": {"precision_pct": 60.0}},
            {"at": "2026-08-10T10:01:00+00:00", "type": "decision", "decision": "NO_TRADE", "reason": "sem sinal"},
        ],
    )

    res = test_client.get("/api/operations/lab")

    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "paper_trading"
    assert data["latest_decision"]["title"] == "NO_TRADE"
    assert data["latest_calibration"]["precision_pct"] == 60.0
    assert data["state"]["positions"][0]["symbol"] == "AAPL"
    assert data["readiness"]["trade_automation_allowed"] is False


def test_operations_health_marks_yfinance_as_required(client, monkeypatch):
    test_client, _ = client
    dates = pd.date_range("2026-01-01", periods=2, freq="D", tz="UTC")
    history = pd.DataFrame(
        {
            "open": [100, 101],
            "high": [101, 102],
            "low": [99, 100],
            "close": [100, 101],
            "volume": [1000, 1100],
        },
        index=dates,
    )
    monkeypatch.setattr("app.routers.operations.market_data_service.get_bars", lambda *args, **kwargs: history)

    res = test_client.get("/api/operations/health")

    assert res.status_code == 200
    providers = res.json()["providers"]
    assert providers["yfinance_enabled"] is True
    assert providers["yfinance_required_for_technical_analysis"] is True
    assert providers["yfinance_available"] is True
    assert providers["yfinance_role"] == "historical_ohlcv"


def test_share_watchlist_public_read_only(client):
    test_client, _ = client
    test_client.post("/api/watchlist", json={"symbol": "AAPL", "label": "Apple"})

    share = test_client.post("/api/share/watchlist")

    assert share.status_code == 200
    public = test_client.get(f"/api/share/{share.json()['slug']}")
    assert public.status_code == 200
    assert public.json()["rows"][0]["symbol"] == "AAPL"


def test_alerts_filter_by_symbol(client):
    test_client, Session = client
    db = Session()
    db.add(AlertLog(user_id=1, symbol="AAPL", rule_type="PRICE_ABOVE", message="AAPL subiu"))
    db.add(AlertLog(user_id=1, symbol="MSFT", rule_type="PRICE_ABOVE", message="MSFT subiu"))
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
    db.add(AlertLog(user_id=1, symbol="AAPL", rule_type="PRICE_ABOVE", message="a"))
    db.add(AlertLog(user_id=1, symbol="AAPL", rule_type="RSI_OVERBOUGHT", message="b"))
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
    db.add(AlertLog(symbol="AAPL", rule_type="PRICE_ABOVE", message="a"))
    db.add(AlertLog(symbol="MSFT", rule_type="PRICE_ABOVE", message="b"))
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
    item = WatchlistItem(symbol="NVDA", label="Nvidia")
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

    monkeypatch.setattr("app.copilot.market_data_service.get_bars", lambda *args, **kwargs: history)

    res = test_client.post(
        "/api/copilot/analyze",
        json={"symbol": "NVDA", "capital_usd": 20000, "risk_budget_pct": 1, "question": "vale olhar?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["symbol"] == "NVDA"
    assert "votes" in data
    assert len(data["votes"]) == 5
    assert data["trade_plan"]["available"] is True
    assert data["trade_plan"]["target_1_price"] > data["trade_plan"]["entry_price"]
    assert data["trade_plan"]["stop_price"] < data["trade_plan"]["entry_price"]
    assert "simulation" in data


def test_trader_profile_endpoint_with_closed_trade(client):
    test_client, Session = client
    db = Session()
    db.add(
        Transaction(
            user_id=1,
            symbol="NVDA",
            side=TransactionSide.BUY,
            quantity=10,
            price=100,
            executed_at=datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
        )
    )
    db.add(
        Transaction(
            user_id=1,
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


def test_positions_fallback_to_market_history_without_snapshot(client, monkeypatch):
    test_client, Session = client
    db = Session()
    db.add(WatchlistItem(symbol="SNAP", label="Snap"))
    db.add(
        Transaction(
            user_id=1,
            symbol="SNAP",
            side=TransactionSide.BUY,
            quantity=10,
            price=5,
            executed_at=datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
        )
    )
    db.commit()
    db.close()

    dates = pd.date_range("2026-01-01", periods=2, freq="D", tz="UTC")
    history = pd.DataFrame(
        {
            "open": [5, 5.2],
            "high": [5.3, 5.6],
            "low": [4.9, 5.1],
            "close": [5.1, 5.5],
            "volume": [1000, 1200],
        },
        index=dates,
    )
    monkeypatch.setattr("app.routers.positions.market_data_service.get_bars", lambda *args, **kwargs: history)

    res = test_client.get("/api/positions")

    assert res.status_code == 200
    data = res.json()
    assert data[0]["current_price"] == 5.5
    assert data[0]["unrealized_pnl"] == 5


def test_technical_desk_analysis_levels_and_setups(client, monkeypatch):
    test_client, _ = client
    dates = pd.date_range("2026-01-01", periods=80, freq="D", tz="UTC")
    history = pd.DataFrame(
        {
            "open": [100 + i * 0.2 for i in range(80)],
            "high": [101 + i * 0.2 for i in range(80)],
            "low": [99 + i * 0.2 for i in range(80)],
            "close": [100 + i * 0.2 for i in range(80)],
            "volume": [1000 + i * 10 for i in range(80)],
        },
        index=dates,
    )
    monkeypatch.setattr("app.routers.technical.market_data_service.get_bars", lambda *args, **kwargs: history)

    level = test_client.post(
        "/api/technical/levels",
        json={"symbol": "NVDA", "kind": "SUPPORT", "label": "Fundo relevante", "price": 112.5},
    )
    assert level.status_code == 201
    assert level.json()["symbol"] == "NVDA"

    setup = test_client.post(
        "/api/technical/setups",
        json={
            "symbol": "NVDA",
            "direction": "LONG",
            "entry_price": 116,
            "stop_price": 112,
            "target_price": 124,
            "thesis": "Continuidade acima das medias",
        },
    )
    assert setup.status_code == 201

    analysis = test_client.get("/api/technical/analysis/NVDA")
    assert analysis.status_code == 200
    data = analysis.json()
    assert data["symbol"] == "NVDA"
    assert data["bias"] in {"ALTISTA", "BAIXISTA", "NEUTRO"}
    assert data["atr_14"] is not None
    assert data["atr_pct"] is not None
    assert data["annualized_volatility_20"] is not None
    assert data["avg_range_pct_20"] is not None
    assert data["volatility_label"] in {"Baixa", "Media", "Alta", "Muito alta", "Sem leitura"}
    assert data["suggested_shares_200_usd"] >= 0
    assert data["levels"][0]["label"] == "Fundo relevante"
    assert data["setups"][0]["risk_reward"] if "risk_reward" in data["setups"][0] else data["risk_reward"] == 2.0

    assert test_client.delete(f"/api/technical/levels/{level.json()['id']}").status_code == 204
    assert test_client.delete(f"/api/technical/setups/{setup.json()['id']}").status_code == 204

    refreshed = test_client.get("/api/technical/analysis/NVDA").json()
    assert refreshed["levels"] == []
    assert refreshed["setups"] == []


def test_decision_desk_generates_and_records_recommendations(client, monkeypatch):
    test_client, _ = client
    rows = 240
    history = pd.DataFrame(
        {
            "open": [100 + i * 0.2 for i in range(rows)],
            "high": [102 + i * 0.2 for i in range(rows)],
            "low": [99 + i * 0.2 for i in range(rows)],
            "close": [100 + i * 0.2 for i in range(rows)],
            "volume": [1000 + i for i in range(rows)],
        },
        index=pd.date_range("2025-01-01", periods=rows, freq="D"),
    )
    monkeypatch.setattr("app.paper_simulator._history", lambda symbol, period="1y": history)
    # The scenario verifies decision recording, not external provider health.
    # Keep it deterministic and cover data-quality behavior in its own tests.
    monkeypatch.setattr(
        "app.decision_engine.quality_gate",
        lambda *args, **kwargs: {"allowed": True, "confidence": "HIGH", "reason": ""},
    )

    data = test_client.get("/api/decision-desk/recommendations?record=true").json()

    assert "recommendations" in data
    assert data["recorded"] == len(data["recommendations"])
    assert data["recommendations"][0]["fair_reason"]

    history_rows = test_client.get("/api/decision-desk/history").json()
    assert len(history_rows) >= 1
    assert history_rows[0]["evidence"]


def test_daily_market_summary_endpoint(client, monkeypatch):
    test_client, Session = client
    db = Session()
    db.add(WatchlistItem(symbol="NVDA", label="Nvidia"))
    db.commit()
    db.close()

    dates = pd.date_range("2026-01-01", periods=80, freq="D", tz="UTC")
    history = pd.DataFrame(
        {
            "open": [100 + i * 0.2 for i in range(80)],
            "high": [101 + i * 0.2 for i in range(80)],
            "low": [99 + i * 0.2 for i in range(80)],
            "close": [100 + i * 0.2 for i in range(80)],
            "volume": [1000 + i * 10 for i in range(80)],
        },
        index=dates,
    )
    monkeypatch.setattr("app.reports.market_data_service.get_bars", lambda *args, **kwargs: history)

    res = test_client.get("/api/reports/daily-summary")

    assert res.status_code == 200
    data = res.json()
    assert "market_tone" in data
    assert data["key_takeaways"]
    rows = data["opportunities"] + data["risks"] + data["watch"]
    assert rows[0]["symbol"] == "NVDA"
    assert data["action_plan"]


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
