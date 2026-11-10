import hashlib
import hmac
import json
import time
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth as auth_module
from app import billing
from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import AlertLog, Transaction, TransactionSide, User, WatchlistItem, utcnow


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    auth_module._failed_attempts.clear()
    billing._llm_usage.clear()
    billing._hits.clear()
    yield TestClient(app), Session
    app.dependency_overrides.clear()


def _signup(c, name):
    res = c.post(
        "/api/auth/cadastro",
        json={"username": name, "email": f"{name}@t.com", "password": "senha12345", "accept_terms": True},
    )
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _rule(item_id):
    return {
        "watchlist_item_id": item_id,
        "logic": "ALL",
        "cooldown_minutes": 60,
        "conditions": [{"rule_type": "PRICE_ABOVE", "threshold": 1}],
    }


def _make_free(Session, name):
    db = Session()
    user = db.query(User).filter(User.username == name).first()
    user.plan = "free"
    user.trial_ends_at = None
    db.commit()
    db.close()


# --- plano efetivo ---------------------------------------------------------------------------


def test_effective_plan_rules():
    assert billing.effective_plan(User(plan="free")) == "free"
    assert billing.effective_plan(User(plan="pro")) == "pro"
    assert billing.effective_plan(User(plan="free", trial_ends_at=utcnow() + timedelta(days=1))) == "pro"
    assert billing.effective_plan(User(plan="free", trial_ends_at=utcnow() - timedelta(days=1))) == "free"


# --- isolamento entre usuários ---------------------------------------------------------------


def test_users_cannot_see_or_touch_each_others_data(client):
    c, Session = client
    dono = _signup(c, "dono")
    ana = _signup(c, "ana")

    item = c.post("/api/watchlist", json={"symbol": "AAPL"}, headers=dono).json()
    c.post("/api/watchlist", json={"symbol": "AAPL"}, headers=ana)  # mesmo ticker, outro dono: permitido

    assert [i["symbol"] for i in c.get("/api/watchlist", headers=ana).json()] == ["AAPL"]
    assert c.delete(f"/api/watchlist/{item['id']}", headers=ana).status_code == 404
    rule = _rule(item["id"])
    assert c.post(f"/api/watchlist/{item['id']}/rules", json=rule, headers=ana).status_code == 404
    assert c.get(f"/api/watchlist/{item['id']}/rules", headers=ana).status_code == 404

    own_rule = c.post(f"/api/watchlist/{item['id']}/rules", json=rule, headers=dono).json()
    assert c.delete(f"/api/watchlist/rules/{own_rule['id']}", headers=ana).status_code == 404

    tx = {"symbol": "AAPL", "side": "BUY", "quantity": 1, "price": 10, "executed_at": "2026-01-01T00:00:00Z"}
    created = c.post("/api/positions/transactions", json=tx, headers=dono).json()
    assert c.get("/api/positions", headers=ana).json() == []
    assert c.delete(f"/api/positions/transactions/{created['id']}", headers=ana).status_code == 404
    assert len(c.get("/api/positions", headers=dono).json()) == 1

    db = Session()
    dono_id = db.query(User).filter(User.username == "dono").first().id
    db.add(AlertLog(user_id=dono_id, symbol="AAPL", rule_type="X", message="so do dono"))
    db.commit()
    db.close()
    assert c.get("/api/alerts", headers=ana).json() == []
    assert len(c.get("/api/alerts", headers=dono).json()) == 1
    assert c.get("/api/dashboard-summary", headers=ana).json()["alerts"] == []


# --- limites e recursos Pro ------------------------------------------------------------------


def test_free_plan_limits_symbols_and_rules(client):
    c, Session = client
    _signup(c, "dono")
    ana = _signup(c, "ana")
    _make_free(Session, "ana")

    ids = []
    for sym in ["AAPL", "MSFT", "NVDA"]:
        res = c.post("/api/watchlist", json={"symbol": sym}, headers=ana)
        assert res.status_code == 201
        ids.append(res.json()["id"])
    blocked = c.post("/api/watchlist", json={"symbol": "TSLA"}, headers=ana)
    assert blocked.status_code == 402
    # reativar/atualizar um que já existe não conta como novo
    assert c.post("/api/watchlist", json={"symbol": "AAPL", "label": "x"}, headers=ana).status_code == 201

    assert c.post(f"/api/watchlist/{ids[0]}/rules", json=_rule(ids[0]), headers=ana).status_code == 201
    assert c.post(f"/api/watchlist/{ids[1]}/rules", json=_rule(ids[1]), headers=ana).status_code == 201
    assert c.post(f"/api/watchlist/{ids[2]}/rules", json=_rule(ids[2]), headers=ana).status_code == 402


def test_symbol_validation(client):
    c, _ = client
    h = _signup(c, "dono")
    assert c.post("/api/watchlist", json={"symbol": "bad symbol!"}, headers=h).status_code == 422


def test_pro_features_return_402_for_free_users_and_work_for_trial(client):
    c, Session = client
    _signup(c, "dono")
    ana = _signup(c, "ana")

    # em teste: libera
    assert c.get("/api/morning-report/today", headers=ana).status_code == 404  # acesso ok, sem relatório ainda
    _make_free(Session, "ana")
    for method, path in [
        ("get", "/api/reports/pdf"),
        ("get", "/api/reports/export.json"),
        ("get", "/api/morning-report/today"),
        ("get", "/api/research/panel/AAPL"),
        ("get", "/api/research/study"),
        ("post", "/api/assistant/ask"),
        ("post", "/api/copilot/analyze"),
        ("post", "/api/auth/telegram/link-code"),
    ]:
        res = getattr(c, method)(path, headers=ana, **({"json": {"question": "oi"}} if method == "post" else {}))
        assert res.status_code == 402, (path, res.status_code)

    status = c.get("/api/billing/status", headers=ana).json()
    assert status["plan"] == "free" and status["limits"]["max_symbols"] == settings.free_max_symbols


def test_public_plans_endpoint(client):
    c, _ = client
    data = c.get("/api/billing/plans").json()
    assert data["free"]["max_symbols"] == settings.free_max_symbols
    assert data["pro"]["max_symbols"] == settings.pro_max_symbols
    assert "price_label" in data["pro"]


def test_llm_daily_quota(client, monkeypatch):
    c, _ = client
    h = _signup(c, "dono")
    monkeypatch.setattr(settings, "llm_daily_limit", 2)
    from unittest.mock import AsyncMock, patch

    with patch("app.routers.assistant.answer_question", new=AsyncMock(return_value="ok")):
        codes = [c.post("/api/assistant/ask", json={"question": "oi"}, headers=h).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


# --- Telegram --------------------------------------------------------------------------------


def test_telegram_link_code_and_unlink(client):
    c, Session = client
    h = _signup(c, "dono")
    code = c.post("/api/auth/telegram/link-code", headers=h).json()["code"]
    assert len(code) == 8
    db = Session()
    assert db.query(User).filter(User.telegram_link_code == code).first() is not None
    db.close()
    assert c.delete("/api/auth/telegram", headers=h).status_code == 204


# --- Stripe ----------------------------------------------------------------------------------


def _signed(payload: dict, secret: str) -> tuple[bytes, str]:
    body = json.dumps(payload).encode()
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return body, f"t={ts},v1={sig}"


def _sub_event(kind, customer, status, sub_id="sub_1"):
    return {
        "id": "evt_1",
        "object": "event",
        "type": kind,
        "data": {
            "object": {
                "id": sub_id,
                "object": "subscription",
                "customer": customer,
                "status": status,
                "current_period_end": int(time.time()) + 86400 * 30,
            }
        },
    }


def test_webhook_rejects_bad_signature(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
    res = c.post("/api/billing/webhook", content=b"{}", headers={"Stripe-Signature": "t=1,v1=abc"})
    assert res.status_code == 400


def test_webhook_activates_and_cancels_subscription(client, monkeypatch):
    c, Session = client
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
    _signup(c, "dono")
    ana = _signup(c, "ana")
    _make_free(Session, "ana")
    db = Session()
    db.query(User).filter(User.username == "ana").first().stripe_customer_id = "cus_ana"
    db.commit()
    db.close()

    body, sig = _signed(_sub_event("customer.subscription.created", "cus_ana", "active"), "whsec_test")
    assert c.post("/api/billing/webhook", content=body, headers={"Stripe-Signature": sig}).status_code == 200
    status = c.get("/api/billing/status", headers=ana).json()
    assert status["plan"] == "pro" and status["paid"] is True and status["subscription_status"] == "active"
    assert status["current_period_end"]

    body, sig = _signed(_sub_event("customer.subscription.deleted", "cus_ana", "canceled"), "whsec_test")
    assert c.post("/api/billing/webhook", content=body, headers={"Stripe-Signature": sig}).status_code == 200
    status = c.get("/api/billing/status", headers=ana).json()
    assert status["plan"] == "free" and status["paid"] is False


def test_webhook_unknown_customer_is_ignored(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
    body, sig = _signed(_sub_event("customer.subscription.updated", "cus_x", "active"), "whsec_test")
    assert c.post("/api/billing/webhook", content=body, headers={"Stripe-Signature": sig}).status_code == 200


def test_checkout_disabled_without_stripe_config(client, monkeypatch):
    c, _ = client
    h = _signup(c, "dono")
    ana = _signup(c, "ana")
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    assert c.post("/api/billing/checkout", headers=ana).status_code == 503
    assert c.get("/api/billing/status", headers=h).json()["checkout_enabled"] is False


def test_checkout_creates_customer_and_session(client, monkeypatch):
    c, Session = client
    _signup(c, "dono")
    ana = _signup(c, "ana")
    _make_free(Session, "ana")
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(settings, "stripe_price_id", "price_x")

    calls = {}

    class FakeStripe:
        class Customer:
            @staticmethod
            def create(**kw):
                calls["customer"] = kw
                return {"id": "cus_new"}

        class checkout:
            class Session:
                @staticmethod
                def create(**kw):
                    calls["session"] = kw
                    return {"url": "https://checkout.stripe.test/s/1"}

    monkeypatch.setattr(billing, "_stripe", lambda: FakeStripe)
    res = c.post("/api/billing/checkout", headers=ana)
    assert res.status_code == 200 and res.json()["url"].startswith("https://checkout.stripe.test")
    assert calls["customer"]["email"] == "ana@t.com"
    assert calls["session"]["customer"] == "cus_new"
    assert calls["session"]["line_items"] == [{"price": "price_x", "quantity": 1}]
    assert calls["session"]["mode"] == "subscription"


def test_admin_can_set_plan_manually(client):
    c, Session = client
    admin = _signup(c, "dono")
    ana = _signup(c, "ana")
    _make_free(Session, "ana")
    db = Session()
    ana_id = db.query(User).filter(User.username == "ana").first().id
    db.close()

    assert c.patch(f"/api/auth/usuarios/{ana_id}/plano", json={"plan": "pro"}, headers=ana).status_code == 403
    res = c.patch(f"/api/auth/usuarios/{ana_id}/plano", json={"plan": "pro"}, headers=admin)
    assert res.status_code == 200 and res.json()["paid"] is True
    assert c.patch(f"/api/auth/usuarios/{ana_id}/plano", json={"plan": "enterprise"}, headers=admin).status_code == 422


def test_cannot_delete_account_with_active_subscription(client):
    c, Session = client
    _signup(c, "dono")
    ana = _signup(c, "ana")
    db = Session()
    u = db.query(User).filter(User.username == "ana").first()
    u.plan, u.stripe_subscription_id = "pro", "sub_1"
    db.commit()
    db.close()
    assert c.delete("/api/auth/me", headers=ana).status_code == 400


def test_trial_end_is_serialized_as_utc(client):
    c, _ = client
    _signup(c, "dono")
    user = c.post(
        "/api/auth/cadastro",
        json={"username": "ana", "email": "ana@t.com", "password": "senha12345", "accept_terms": True},
    ).json()["user"]
    assert user["trial_ends_at"].endswith("Z") or user["trial_ends_at"].endswith("+00:00")
