from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.main import app
from app.models import User
from app.opportunity import Approval, SetupState, Transition
from app.opportunity_ledger import record_transition


@pytest.fixture()
def client():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(User(id=1, username="qa", password_hash="x"))
    db.commit()
    for at, frm, to, approval in [
        ("2026-10-05T10:00:00+00:00", SetupState.IDLE, SetupState.BREAK_DETECTED, Approval.SHADOW),
        ("2026-10-05T10:20:00+00:00", SetupState.WAITING_CONFIRMATION_2, SetupState.READY_TO_ENTER, Approval.SHADOW),
    ]:
        record_transition(db, Transition(at=at, from_state=frm, to_state=to, reason=to.value, direction="long",
                                         payload={"opportunity_id": "gold:1", "stop": 10.0, "reference_close": 12.0,
                                                  "target_r": 1.5, "max_hold_minutes": 240}),
                          setup="gold_fakeout_open", setup_version="v", symbol="XAUUSD.s", mode="SHADOW", approval=approval)
    db.close()

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_timeline_changes_and_chain(client):
    events = client.get("/api/opportunities/timeline", params={"opportunity_id": "gold:1"}).json()["events"]
    assert [e["state"] for e in events] == ["BREAK_DETECTED", "READY_TO_ENTER"]
    assert client.get("/api/opportunities/ledger/verify").json()["ok"] is True
    changes = client.get("/api/opportunities/changes", params={"since_minutes": 10_000}).json()
    assert changes["event_count"] >= 0


def test_paper_feedback_refused_while_setup_is_shadow(client):
    res = client.post("/api/opportunities/gold:1/paper", json={"decision": "OPERATED", "executed_price": 12.3})
    assert res.status_code == 409
    assert client.post("/api/opportunities/unknown/paper", json={"decision": "SKIPPED"}).status_code == 404


def test_oneb_ai_endpoint_falls_back_without_llm(client, monkeypatch):
    from app.oneb_ai import agent

    monkeypatch.setattr(agent, "is_configured", lambda: False)
    body = client.post("/api/opportunities/ai/ask", json={"question": "Existe oportunidade?"}).json()
    assert body["fallback_used"] is True and body["model"] == "template"
    assert body["answer"]["conclusion"]


def test_list_hides_levels_for_shadow_setups(client):
    [opp] = client.get("/api/opportunities").json()["opportunities"]
    assert opp["state"] == "READY_TO_ENTER" and opp["approval"] == "SHADOW"
    assert opp["levels"] is None and opp["research_plan"]["stop"] == 10.0
