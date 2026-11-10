from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.main import app
from app.models import PriceSnapshot, WatchlistItem


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
