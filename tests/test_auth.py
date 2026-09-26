import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth as auth_module
from app.db import Base, get_db
from app.main import app
from app.models import LoginAttempt, RefreshToken, User

REFRESH_HEADER = {"X-Refresh-Request": "1"}


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

    test_client = TestClient(app)
    yield test_client, TestingSession

    app.dependency_overrides.clear()


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_user(Session, username="pai", password="senha12345", is_admin=True) -> None:
    db = Session()
    db.add(User(username=username, password_hash=auth_module.hash_password(password), is_admin=is_admin))
    db.commit()
    db.close()


# --- Contas e privilégios -----------------------------------------------------------


def test_cadastro_never_grants_admin(client):
    """Cadastro público fazia do primeiro usuário um admin — quem chegasse primeiro num
    deploy novo ganhava controle total. Não pode conceder admin, primeiro usuário ou não."""
    test_client, Session = client
    res = test_client.post("/api/auth/cadastro", json={"username": "primeiro", "password": "senha12345"})
    assert res.status_code == 201
    assert res.json()["user"]["is_admin"] is False

    db = Session()
    assert db.query(User).filter(User.username == "primeiro").first().is_admin is False
    db.close()


def test_ensure_admin_bootstrap_creates_admin_when_configured(client, monkeypatch):
    _, Session = client
    monkeypatch.setattr(auth_module.settings, "admin_bootstrap_username", "dono")
    monkeypatch.setattr(auth_module.settings, "admin_bootstrap_password", "senha12345")

    db = Session()
    auth_module.ensure_admin_bootstrap(db)
    db.close()

    db = Session()
    user = db.query(User).filter(User.username == "dono").first()
    assert user is not None and user.is_admin is True
    db.close()


def test_ensure_admin_bootstrap_does_nothing_without_config(client):
    _, Session = client
    db = Session()
    auth_module.ensure_admin_bootstrap(db)
    assert db.query(User).count() == 0
    db.close()


def test_ensure_admin_bootstrap_skips_when_users_already_exist(client, monkeypatch):
    _, Session = client
    _make_user(Session, "existente", is_admin=False)
    monkeypatch.setattr(auth_module.settings, "admin_bootstrap_username", "dono")
    monkeypatch.setattr(auth_module.settings, "admin_bootstrap_password", "senha12345")

    db = Session()
    auth_module.ensure_admin_bootstrap(db)
    assert db.query(User).filter(User.username == "dono").first() is None
    db.close()


# --- Access token e sessão ----------------------------------------------------------


def test_login_returns_access_token_and_sets_httponly_refresh_cookie(client):
    test_client, Session = client
    _make_user(Session)

    res = test_client.post("/api/auth/login", json={"username": "pai", "password": "senha12345"})
    assert res.status_code == 200
    assert res.json()["access_token"]

    assert res.cookies.get(auth_module.settings.refresh_cookie_name)
    set_cookie = res.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie
    assert "SameSite=strict" in set_cookie.replace("samesite", "SameSite")


def test_access_token_is_short_lived(client):
    """Era um JWT de 7 dias em localStorage; agora expira em minutos e vive em memória."""
    assert auth_module.settings.access_token_expire_minutes <= 60


def test_login_success_returns_token_that_works_on_protected_route(client):
    test_client, Session = client
    _make_user(Session)

    token = test_client.post(
        "/api/auth/login", json={"username": "pai", "password": "senha12345"}
    ).json()["access_token"]

    test_client.cookies.clear()  # prova que o bearer funciona sozinho, sem cookie
    me = test_client.get("/api/auth/me", headers=_auth_headers(token))
    assert me.status_code == 200
    assert me.json()["username"] == "pai"
    assert test_client.get("/api/watchlist", headers=_auth_headers(token)).status_code == 200


def test_expired_access_token_is_rejected(client, monkeypatch):
    test_client, Session = client
    _make_user(Session)
    monkeypatch.setattr(auth_module.settings, "access_token_expire_minutes", -1)

    expired = auth_module.create_access_token(1)
    assert test_client.get("/api/auth/me", headers=_auth_headers(expired)).status_code == 401


def test_protected_route_rejects_missing_token(client):
    test_client, _ = client
    assert test_client.get("/api/dashboard-summary").status_code == 401


def test_protected_route_rejects_garbage_token(client):
    test_client, _ = client
    assert test_client.get("/api/dashboard-summary", headers=_auth_headers("not-a-real-token")).status_code == 401


# --- Refresh: rotação, reuso, revogação ---------------------------------------------


def test_refresh_issues_new_access_token_and_rotates_the_cookie(client):
    test_client, Session = client
    _make_user(Session)

    login = test_client.post("/api/auth/login", json={"username": "pai", "password": "senha12345"})
    first_cookie = login.cookies.get(auth_module.settings.refresh_cookie_name)

    refreshed = test_client.post("/api/auth/refresh", headers=REFRESH_HEADER)
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]

    second_cookie = refreshed.cookies.get(auth_module.settings.refresh_cookie_name)
    assert second_cookie and second_cookie != first_cookie


def test_rotated_refresh_token_cannot_be_reused(client):
    """Reuso de um token já rotacionado indica credencial copiada: a família inteira cai."""
    test_client, Session = client
    _make_user(Session)

    login = test_client.post("/api/auth/login", json={"username": "pai", "password": "senha12345"})
    stolen = login.cookies.get(auth_module.settings.refresh_cookie_name)

    assert test_client.post("/api/auth/refresh", headers=REFRESH_HEADER).status_code == 200

    test_client.cookies.set(auth_module.settings.refresh_cookie_name, stolen)
    assert test_client.post("/api/auth/refresh", headers=REFRESH_HEADER).status_code == 401

    db = Session()
    assert db.query(RefreshToken).filter(RefreshToken.revoked_at.is_(None)).count() == 0
    db.close()


def test_refresh_without_cookie_is_rejected(client):
    test_client, _ = client
    assert test_client.post("/api/auth/refresh", headers=REFRESH_HEADER).status_code == 401


def test_refresh_requires_the_anti_csrf_header(client):
    test_client, Session = client
    _make_user(Session)
    test_client.post("/api/auth/login", json={"username": "pai", "password": "senha12345"})

    assert test_client.post("/api/auth/refresh").status_code == 403


def test_logout_revokes_the_whole_refresh_family(client):
    test_client, Session = client
    _make_user(Session)

    login = test_client.post("/api/auth/login", json={"username": "pai", "password": "senha12345"})
    original = login.cookies.get(auth_module.settings.refresh_cookie_name)
    test_client.post("/api/auth/refresh", headers=REFRESH_HEADER)

    assert test_client.post("/api/auth/logout", headers=REFRESH_HEADER).status_code == 204

    # nem o token atual nem qualquer rotação anterior voltam a servir
    assert test_client.post("/api/auth/refresh", headers=REFRESH_HEADER).status_code == 401
    test_client.cookies.set(auth_module.settings.refresh_cookie_name, original)
    assert test_client.post("/api/auth/refresh", headers=REFRESH_HEADER).status_code == 401


def test_expired_refresh_token_is_rejected(client, monkeypatch):
    test_client, Session = client
    _make_user(Session)
    monkeypatch.setattr(auth_module.settings, "refresh_token_expire_days", -1)

    test_client.post("/api/auth/login", json={"username": "pai", "password": "senha12345"})
    assert test_client.post("/api/auth/refresh", headers=REFRESH_HEADER).status_code == 401


def test_refresh_tokens_are_never_stored_in_plaintext(client):
    test_client, Session = client
    _make_user(Session)

    login = test_client.post("/api/auth/login", json={"username": "pai", "password": "senha12345"})
    raw = login.cookies.get(auth_module.settings.refresh_cookie_name)

    db = Session()
    stored = {row.token_hash for row in db.query(RefreshToken).all()}
    db.close()
    assert raw not in stored


# --- Autorização --------------------------------------------------------------------


def test_usuarios_requires_admin(client):
    test_client, Session = client
    _make_user(Session, "comum", is_admin=False)

    token = test_client.post(
        "/api/auth/login", json={"username": "comum", "password": "senha12345"}
    ).json()["access_token"]
    assert test_client.get("/api/auth/usuarios", headers=_auth_headers(token)).status_code == 403


def test_non_admin_cannot_create_users(client):
    test_client, Session = client
    _make_user(Session, "comum", is_admin=False)

    token = test_client.post(
        "/api/auth/login", json={"username": "comum", "password": "senha12345"}
    ).json()["access_token"]
    res = test_client.post(
        "/api/auth/usuarios",
        json={"username": "novo", "password": "outrasenha1", "is_admin": True},
        headers=_auth_headers(token),
    )
    assert res.status_code == 403


def test_admin_can_create_new_user_via_usuarios_endpoint(client):
    test_client, Session = client
    _make_user(Session, "admin")

    token = test_client.post(
        "/api/auth/login", json={"username": "admin", "password": "senha12345"}
    ).json()["access_token"]
    res = test_client.post(
        "/api/auth/usuarios",
        json={"username": "novo", "password": "outrasenha1", "is_admin": False},
        headers=_auth_headers(token),
    )
    assert res.status_code == 201

    db = Session()
    assert db.query(User).filter(User.username == "novo").first() is not None
    db.close()


# --- Rate limiting ------------------------------------------------------------------


def test_login_wrong_password_rejected(client):
    test_client, Session = client
    _make_user(Session)
    assert test_client.post("/api/auth/login", json={"username": "pai", "password": "errada"}).status_code == 401


def test_login_rate_limit_locks_out_after_repeated_failures(client):
    test_client, Session = client
    _make_user(Session)

    for _ in range(5):
        test_client.post("/api/auth/login", json={"username": "pai", "password": "errada"})

    res = test_client.post("/api/auth/login", json={"username": "pai", "password": "senha12345"})
    assert res.status_code == 429


def test_login_rate_limit_is_persisted_in_the_database(client):
    """O lockout antigo vivia num dict do processo: zerava a cada restart e cada réplica
    tinha o seu. Agora tem que estar legível direto na tabela."""
    test_client, Session = client
    _make_user(Session)

    for _ in range(5):
        test_client.post("/api/auth/login", json={"username": "pai", "password": "errada"})

    db = Session()
    assert db.query(LoginAttempt).filter(LoginAttempt.username == "pai").count() == 5
    db.close()


# --- Reset de senha administrativo --------------------------------------------------


def test_admin_reset_password_keeps_the_same_user_id(client):
    """O fluxo antigo era "admin recria o usuario no banco", o que trocava o id e
    descartava watchlist/posicoes/historico presos a ele. O reset preserva a identidade."""
    test_client, Session = client
    _make_user(Session, "admin")
    _make_user(Session, "aluno", is_admin=False)

    db = Session()
    aluno_id = db.query(User).filter(User.username == "aluno").first().id
    db.close()

    token = test_client.post(
        "/api/auth/login", json={"username": "admin", "password": "senha12345"}
    ).json()["access_token"]

    res = test_client.post(
        f"/api/auth/usuarios/{aluno_id}/senha",
        json={"password": "senha-nova-98765"},
        headers=_auth_headers(token),
    )
    assert res.status_code == 200
    assert res.json()["id"] == aluno_id

    test_client.cookies.clear()
    assert test_client.post(
        "/api/auth/login", json={"username": "aluno", "password": "senha-nova-98765"}
    ).status_code == 200
    assert test_client.post(
        "/api/auth/login", json={"username": "aluno", "password": "senha12345"}
    ).status_code == 401


def test_password_reset_revokes_the_users_sessions(client):
    test_client, Session = client
    _make_user(Session, "admin")
    _make_user(Session, "aluno", is_admin=False)

    db = Session()
    aluno_id = db.query(User).filter(User.username == "aluno").first().id
    db.close()

    # aluno logado antes do reset
    test_client.post("/api/auth/login", json={"username": "aluno", "password": "senha12345"})
    assert test_client.post("/api/auth/refresh", headers=REFRESH_HEADER).status_code == 200

    admin_token = test_client.post(
        "/api/auth/login", json={"username": "admin", "password": "senha12345"}
    ).json()["access_token"]
    test_client.post(
        f"/api/auth/usuarios/{aluno_id}/senha",
        json={"password": "senha-nova-98765"},
        headers=_auth_headers(admin_token),
    )

    db = Session()
    ativos = (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == aluno_id, RefreshToken.revoked_at.is_(None))
        .count()
    )
    db.close()
    assert ativos == 0


def test_non_admin_cannot_reset_anyone_password(client):
    test_client, Session = client
    _make_user(Session, "comum", is_admin=False)
    _make_user(Session, "vitima", is_admin=False)

    db = Session()
    vitima_id = db.query(User).filter(User.username == "vitima").first().id
    db.close()

    token = test_client.post(
        "/api/auth/login", json={"username": "comum", "password": "senha12345"}
    ).json()["access_token"]

    res = test_client.post(
        f"/api/auth/usuarios/{vitima_id}/senha",
        json={"password": "senha-invadida-1"},
        headers=_auth_headers(token),
    )
    assert res.status_code == 403


def test_password_reset_clears_the_lockout(client):
    test_client, Session = client
    _make_user(Session, "admin")
    _make_user(Session, "travado", is_admin=False)

    db = Session()
    travado_id = db.query(User).filter(User.username == "travado").first().id
    db.close()

    for _ in range(5):
        test_client.post("/api/auth/login", json={"username": "travado", "password": "errada"})
    assert test_client.post(
        "/api/auth/login", json={"username": "travado", "password": "senha12345"}
    ).status_code == 429

    admin_token = test_client.post(
        "/api/auth/login", json={"username": "admin", "password": "senha12345"}
    ).json()["access_token"]
    test_client.post(
        f"/api/auth/usuarios/{travado_id}/senha",
        json={"password": "senha-nova-98765"},
        headers=_auth_headers(admin_token),
    )

    assert test_client.post(
        "/api/auth/login", json={"username": "travado", "password": "senha-nova-98765"}
    ).status_code == 200
