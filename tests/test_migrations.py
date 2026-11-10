from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app import migrations
from app.config import settings

OLD_SCHEMA = [
    "CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(64) NOT NULL, password_hash VARCHAR(255) NOT NULL,"
    " is_admin BOOLEAN NOT NULL, created_at DATETIME NOT NULL)",
    "CREATE UNIQUE INDEX ix_users_username ON users (username)",
    "CREATE TABLE watchlist_items (id INTEGER PRIMARY KEY, symbol VARCHAR(16) NOT NULL, label VARCHAR(64) NOT NULL,"
    " active BOOLEAN NOT NULL, created_at DATETIME NOT NULL)",
    "CREATE UNIQUE INDEX ix_watchlist_items_symbol ON watchlist_items (symbol)",
    "CREATE TABLE price_snapshots (id INTEGER PRIMARY KEY, watchlist_item_id INTEGER NOT NULL REFERENCES watchlist_items (id),"
    " price FLOAT NOT NULL)",
    "CREATE TABLE alert_logs (id INTEGER PRIMARY KEY, symbol VARCHAR(16) NOT NULL, message TEXT NOT NULL)",
    "CREATE TABLE transactions (id INTEGER PRIMARY KEY, symbol VARCHAR(16) NOT NULL, quantity FLOAT NOT NULL)",
    "INSERT INTO users VALUES (1, 'dono', 'h', 1, '2026-01-01'), (2, 'amigo', 'h', 0, '2026-01-02')",
    "INSERT INTO watchlist_items VALUES (10, 'AAPL', 'Apple', 1, '2026-01-01'), (11, 'NVDA', '', 1, '2026-01-01')",
    "INSERT INTO price_snapshots VALUES (1, 10, 150.0)",
    "INSERT INTO alert_logs VALUES (1, 'AAPL', 'subiu')",
    "INSERT INTO transactions VALUES (1, 'AAPL', 5)",
]


def _legacy_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as conn:
        for stmt in OLD_SCHEMA:
            conn.execute(text(stmt))
    return engine


def test_legacy_database_is_migrated_without_losing_data(monkeypatch):
    monkeypatch.setattr(settings, "telegram_chat_id", "999")
    engine = _legacy_engine()
    migrations.run(engine)

    with engine.connect() as conn:
        # dados antigos entregues ao administrador, e filhos continuam apontando para o item
        assert conn.execute(text("SELECT DISTINCT user_id FROM watchlist_items")).scalars().all() == [1]
        assert conn.execute(text("SELECT user_id FROM alert_logs")).scalar() == 1
        assert conn.execute(text("SELECT user_id FROM transactions")).scalar() == 1
        assert conn.execute(
            text("SELECT w.symbol FROM price_snapshots p JOIN watchlist_items w ON w.id = p.watchlist_item_id")
        ).scalar() == "AAPL"
        # quem já usava continua Pro; o Telegram do dono é vinculado
        assert conn.execute(text("SELECT DISTINCT plan FROM users")).scalars().all() == ["pro"]
        assert conn.execute(text("SELECT telegram_chat_id FROM users WHERE id = 1")).scalar() == "999"

    insert = "INSERT INTO watchlist_items (user_id, symbol, label, active, created_at) VALUES (2, 'AAPL', '', 1, 'x')"
    # o mesmo ticker agora pode existir para outro usuário, mas não duplicado no mesmo
    with engine.begin() as conn:
        conn.execute(text(insert))
    try:
        with engine.begin() as conn:
            conn.execute(text(insert))
        raised = False
    except Exception:
        raised = True
    assert raised

    assert {"email", "plan", "stripe_customer_id", "telegram_chat_id"} <= {c["name"] for c in inspect(engine).get_columns("users")}


def test_migration_is_idempotent(monkeypatch):
    monkeypatch.setattr(settings, "telegram_chat_id", "")
    engine = _legacy_engine()
    migrations.run(engine)
    migrations.run(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM watchlist_items")).scalar() == 2
