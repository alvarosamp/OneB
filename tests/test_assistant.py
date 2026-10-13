from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.main import app
from app.models import MacroIntelligenceSnapshot, PriceSnapshot, WatchlistItem


def _macro_payload(now):
    as_of = now.isoformat()
    quality = [{"key": key, "status": "FRESH", "as_of": as_of} for key in ("GOLD", "WTI", "DXY")]
    def window(gold_wti, gold_dxy):
        return {"matrix": [{"key": "GOLD", "values": {"WTI": gold_wti, "DXY": gold_dxy}}]}
    return {
        "data_quality": {"instruments": quality},
        "correlation_windows": {"20": window(0.1, -0.4), "60": window(-0.6, -0.5),
                                "3m": window(-0.3, -0.2), "6m": window(0.2, -0.1)},
        "trends": {"GOLD": {"direction": "ALTA", "change_20d": 3.2, "change_unit": "%"}},
        "daily_moves": {"GOLD": {"move": 0.5, "unit": "%", "as_of": as_of}},
        "relationship_dynamics": [{"left": "GOLD", "right": "WTI", "status": "ENFRAQUECENDO"}],
    }


@pytest.fixture()
def client():
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
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="test-user", is_admin=False)

    test_client = TestClient(app)
    yield test_client, TestingSession

    app.dependency_overrides.clear()


def test_ask_requires_auth(client):
    test_client, _ = client
    app.dependency_overrides.pop(get_current_user, None)
    res = test_client.post("/api/assistant/ask", json={"question": "oi"})
    assert res.status_code == 401


def test_ask_returns_mocked_answer_without_calling_real_api(client):
    test_client, _ = client
    # Never let this test hit the real Anthropic API — patch at the import site
    # inside app.routers.assistant (where `answer_question` was imported into).
    with patch("app.routers.assistant.answer_question", new=AsyncMock(return_value="resposta de teste")):
        res = test_client.post("/api/assistant/ask", json={"question": "por que a AAPL subiu?"})

    assert res.status_code == 200
    assert res.json() == {"answer": "resposta de teste"}


def test_ask_context_includes_watchlist_prices(client):
    test_client, Session = client
    db = Session()
    item = WatchlistItem(symbol="AAPL", label="Apple")
    db.add(item)
    db.commit()
    db.add(PriceSnapshot(watchlist_item_id=item.id, price=200.0, change_pct=1.5, volume=1000))
    db.commit()
    db.close()

    captured_context = {}

    async def fake_answer(question, context):
        captured_context.update(context)
        return "ok"

    with patch("app.routers.assistant.answer_question", new=fake_answer):
        res = test_client.post("/api/assistant/ask", json={"question": "status?"})

    assert res.status_code == 200
    assert captured_context["watchlist"][0]["symbol"] == "AAPL"
    assert captured_context["watchlist"][0]["price"] == 200.0


def test_ask_selects_fresh_context_assets_outside_watchlist(client):
    test_client, Session = client
    now = datetime.now(timezone.utc)
    with Session() as db:
        db.add(WatchlistItem(symbol="XAUUSD", label="Ouro"))
        db.add(MacroIntelligenceSnapshot(snapshot_date=now.date().isoformat(), captured_at=now,
                                         payload=_macro_payload(now)))
        db.commit()
    captured = {}

    async def fake_answer(question, context):
        captured.update(context)
        return "ok"

    with patch("app.routers.assistant.answer_question", new=fake_answer):
        res = test_client.post("/api/assistant/ask", json={"question": "Como está o ouro?"})

    assert res.status_code == 200
    cross = captured["cross_asset_context"]
    assert cross["status"] == "AVAILABLE"
    target = cross["targets"][0]
    assert target["asset"]["key"] == "GOLD"
    assert target["asset"]["outside_watchlist"] is False
    assert {row["asset"]["key"] for row in target["related_assets"]} == {"WTI", "DXY"}
    assert all(row["asset"]["outside_watchlist"] for row in target["related_assets"])
    assert target["related_assets"][0]["correlation_60_sessions"] == -0.6


def test_old_macro_snapshot_is_not_presented_as_current(client):
    test_client, Session = client
    old = datetime.now(timezone.utc) - timedelta(days=8)
    with Session() as db:
        db.add(MacroIntelligenceSnapshot(snapshot_date=old.date().isoformat(), captured_at=old,
                                         payload=_macro_payload(old)))
        db.commit()
    captured = {}

    async def fake_answer(question, context):
        captured.update(context)
        return "ok"

    with patch("app.routers.assistant.answer_question", new=fake_answer):
        test_client.post("/api/assistant/ask", json={"question": "Ouro e petróleo estão correlacionados?"})
    assert captured["cross_asset_context"]["status"] == "STALE"
    assert "correlation_windows" not in captured["cross_asset_context"]


def test_general_question_gets_watched_macro_overview(client):
    from app.assistant_market_context import build_cross_asset_context

    _, Session = client
    now = datetime.now(timezone.utc)
    with Session() as db:
        db.add(MacroIntelligenceSnapshot(snapshot_date=now.date().isoformat(), captured_at=now,
                                         payload=_macro_payload(now)))
        db.commit()
        context = build_cross_asset_context(
            db, "Analise as tendencias do mercado", [{"symbol": "XAUUSD", "label": "Ouro"},
                                                     {"symbol": "CL=F", "label": "Petróleo WTI"}], now=now,
        )
    assert context["status"] == "AVAILABLE"
    assert {row["key"] for row in context["watchlist_overview"]} == {"GOLD", "WTI"}


def test_missing_or_stale_instrument_history_does_not_rank_peers(client):
    from app.assistant_market_context import build_cross_asset_context

    _, Session = client
    now = datetime.now(timezone.utc)
    payload = _macro_payload(now)
    payload["data_quality"]["instruments"][1]["status"] = "STALE"
    with Session() as db:
        db.add(MacroIntelligenceSnapshot(snapshot_date=now.date().isoformat(), captured_at=now, payload=payload))
        db.commit()
        context = build_cross_asset_context(db, "ouro", [{"symbol": "XAUUSD", "label": "Ouro"}], now=now)
    assert [row["asset"]["key"] for row in context["targets"][0]["related_assets"]] == ["DXY"]


def test_currency_pair_is_not_mistaken_for_dollar_index(client):
    from app.assistant_market_context import _mentioned

    assert _mentioned("EUR/Dólar EURUSD=X") == ["EURUSD"]
    assert _mentioned("Índice Dólar") == ["DXY"]


def test_llm_client_returns_none_without_api_key():
    # Sanity check for the graceful-degradation contract: with no API key
    # configured for the active provider, the real client must short-circuit
    # to None instead of trying to make a network call. Force both provider
    # keys empty here regardless of what's in the local .env, so this test
    # can't accidentally hit a real API if a real key is ever configured on
    # the machine running the suite.
    import asyncio

    from app import llm_client
    from app.config import settings

    original = {
        "anthropic_api_key": settings.anthropic_api_key,
        "gemini_api_key": settings.gemini_api_key,
        "groq_api_key": settings.groq_api_key,
        "_anthropic_client": llm_client._anthropic_client,
        "_gemini_configured": llm_client._gemini_configured,
        "_groq_client": llm_client._groq_client,
    }
    settings.anthropic_api_key = ""
    settings.gemini_api_key = ""
    settings.groq_api_key = ""
    llm_client._anthropic_client = None
    llm_client._gemini_configured = False
    llm_client._groq_client = None
    try:
        assert llm_client.is_configured() is False
        result = asyncio.run(llm_client.generate_daily_narrative({"precos": []}))
    finally:
        settings.anthropic_api_key = original["anthropic_api_key"]
        settings.gemini_api_key = original["gemini_api_key"]
        settings.groq_api_key = original["groq_api_key"]
        llm_client._anthropic_client = original["_anthropic_client"]
        llm_client._gemini_configured = original["_gemini_configured"]
        llm_client._groq_client = original["_groq_client"]

    assert result is None
