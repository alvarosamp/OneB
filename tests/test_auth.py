import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth as auth_module
from app.db import Base, get_db
from app.main import app
from app.models import User, WatchlistItem


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
    # Clear any brute-force lockout state left over from other tests (module-level dict).
    auth_module._failed_attempts.clear()

    test_client = TestClient(app)
    yield test_client, TestingSession

    app.dependency_overrides.clear()


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _signup(test_client, username="admin", email=None, **extra):
    body = {
        "username": username,
        "email": email or f"{username}@teste.com",
        "password": "senha12345",
        "accept_terms": True,
    }
    body.update(extra)
    return test_client.post("/api/auth/cadastro", json=body)


def test_cadastro_creates_first_user_as_admin_with_pro(client):
    test_client, Session = client
    res = _signup(test_client)
    assert res.status_code == 201
    data = res.json()
    assert data["user"]["username"] == "admin"
    assert data["user"]["is_admin"] is True
    assert data["user"]["plan"] == "pro"
    assert data["access_token"]

    db = Session()
    user = db.query(User).filter(User.username == "admin").first()
    assert user is not None and user.is_admin is True
    db.close()


def test_cadastro_is_open_and_new_users_get_a_trial(client):
    test_client, _ = client
    _signup(test_client, "dono")
    res = _signup(test_client, "cliente")
    assert res.status_code == 201
    user = res.json()["user"]
    assert user["is_admin"] is False
    assert user["on_trial"] is True and user["plan"] == "pro" and user["paid"] is False
    assert user["trial_ends_at"]


def test_cadastro_requires_terms_and_unique_email(client):
    test_client, _ = client
    assert _signup(test_client, "ana", accept_terms=False).status_code == 400
    assert _signup(test_client, "ana", email="x@teste.com").status_code == 201
    assert _signup(test_client, "bia", email="X@teste.com").status_code == 400  # e-mail repetido
    assert _signup(test_client, "ana", email="y@teste.com").status_code == 400  # usuário repetido
    assert test_client.post(
        "/api/auth/cadastro",
        json={"username": "cris", "email": "invalido", "password": "senha12345", "accept_terms": True},
    ).status_code == 422


def test_login_accepts_email(client):
    test_client, _ = client
    _signup(test_client, "maria", email="maria@teste.com")
    res = test_client.post("/api/auth/login", json={"username": "Maria@Teste.com", "password": "senha12345"})
    assert res.status_code == 200


def test_delete_account_removes_user_data(client):
    test_client, Session = client
    _signup(test_client, "dono")
    token = _signup(test_client, "cliente").json()["access_token"]
    headers = _auth_headers(token)
    test_client.post("/api/watchlist", json={"symbol": "AAPL"}, headers=headers)

    assert test_client.delete("/api/auth/me", headers=headers).status_code == 204
    db = Session()
    assert db.query(User).filter(User.username == "cliente").first() is None
    assert db.query(WatchlistItem).count() == 0
    db.close()
    assert test_client.get("/api/auth/me", headers=headers).status_code == 401


def test_login_success_returns_token_that_works_on_protected_route(client):
    test_client, Session = client
    db = Session()
    db.add(User(username="pai", password_hash=auth_module.hash_password("senha12345"), is_admin=True))
    db.commit()
    db.close()

    res = test_client.post("/api/auth/login", json={"username": "pai", "password": "senha12345"})
    assert res.status_code == 200
    token = res.json()["access_token"]

    me = test_client.get("/api/auth/me", headers=_auth_headers(token))
    assert me.status_code == 200
    assert me.json()["username"] == "pai"

    watchlist = test_client.get("/api/watchlist", headers=_auth_headers(token))
    assert watchlist.status_code == 200


def test_login_wrong_password_rejected(client):
    test_client, Session = client
    db = Session()
    db.add(User(username="pai", password_hash=auth_module.hash_password("senha12345"), is_admin=True))
    db.commit()
    db.close()

    res = test_client.post("/api/auth/login", json={"username": "pai", "password": "errada"})
    assert res.status_code == 401


def test_protected_route_rejects_missing_token(client):
    test_client, _ = client
    res = test_client.get("/api/dashboard-summary")
    assert res.status_code == 401


def test_protected_route_rejects_garbage_token(client):
    test_client, _ = client
    res = test_client.get("/api/dashboard-summary", headers=_auth_headers("not-a-real-token"))
    assert res.status_code == 401


def test_usuarios_requires_admin(client):
    test_client, Session = client
    db = Session()
    db.add(User(username="comum", password_hash=auth_module.hash_password("senha12345"), is_admin=False))
    db.commit()
    db.close()

    login = test_client.post("/api/auth/login", json={"username": "comum", "password": "senha12345"})
    token = login.json()["access_token"]

    res = test_client.get("/api/auth/usuarios", headers=_auth_headers(token))
    assert res.status_code == 403


def test_admin_can_create_new_user_via_usuarios_endpoint(client):
    test_client, Session = client
    db = Session()
    db.add(User(username="admin", password_hash=auth_module.hash_password("senha12345"), is_admin=True))
    db.commit()
    db.close()

    login = test_client.post("/api/auth/login", json={"username": "admin", "password": "senha12345"})
    token = login.json()["access_token"]

    res = test_client.post(
        "/api/auth/usuarios",
        json={"username": "novo", "password": "outrasenha1", "is_admin": False},
        headers=_auth_headers(token),
    )
    assert res.status_code == 201

    db = Session()
    assert db.query(User).filter(User.username == "novo").first() is not None
    db.close()


def test_login_rate_limit_locks_out_after_repeated_failures(client):
    test_client, Session = client
    db = Session()
    db.add(User(username="pai", password_hash=auth_module.hash_password("senha12345"), is_admin=True))
    db.commit()
    db.close()

    for _ in range(5):
        test_client.post("/api/auth/login", json={"username": "pai", "password": "errada"})

    res = test_client.post("/api/auth/login", json={"username": "pai", "password": "senha12345"})
    assert res.status_code == 429
