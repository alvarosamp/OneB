"""Migrações leves, idempotentes, rodadas no startup (não há Alembic neste projeto).

`Base.metadata.create_all` cria tabelas novas, mas não altera as existentes. Estas funções levam
um banco do tempo "um usuário só" para o modelo multiusuário com planos, sem perder dados:

- adiciona as colunas novas (usuários, dono dos dados);
- troca o UNIQUE global de `watchlist_items.symbol` por UNIQUE(user_id, symbol);
- entrega os dados antigos ao primeiro administrador e mantém o plano dele como Pro.
"""
from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine

from app.config import settings

logger = logging.getLogger(__name__)

_USER_COLUMNS = {
    "email": "VARCHAR(254)",
    "accepted_terms_at": "DATETIME",
    "plan": "VARCHAR(16) NOT NULL DEFAULT 'free'",
    "trial_ends_at": "DATETIME",
    "stripe_customer_id": "VARCHAR(64)",
    "stripe_subscription_id": "VARCHAR(64)",
    "subscription_status": "VARCHAR(24) NOT NULL DEFAULT ''",
    "current_period_end": "DATETIME",
    "telegram_chat_id": "VARCHAR(32)",
    "telegram_link_code": "VARCHAR(32)",
}


def _columns(conn: Connection, table: str) -> set[str]:
    return {c["name"] for c in inspect(conn).get_columns(table)}


def _has_table(conn: Connection, table: str) -> bool:
    return inspect(conn).has_table(table)


def _add_column(conn: Connection, table: str, name: str, ddl: str) -> None:
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def _rebuild_watchlist_sqlite(conn: Connection) -> None:
    """Procedimento de 12 passos do SQLite: recria a tabela com UNIQUE(user_id, symbol)."""
    conn.execute(text("PRAGMA foreign_keys=OFF"))
    conn.execute(
        text(
            """
            CREATE TABLE watchlist_items_new (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id INTEGER REFERENCES users (id),
                symbol VARCHAR(16) NOT NULL,
                label VARCHAR(64) NOT NULL,
                active BOOLEAN NOT NULL,
                created_at DATETIME NOT NULL,
                CONSTRAINT uq_watchlist_user_symbol UNIQUE (user_id, symbol)
            )
            """
        )
    )
    conn.execute(
        text(
            "INSERT INTO watchlist_items_new (id, symbol, label, active, created_at) "
            "SELECT id, symbol, label, active, created_at FROM watchlist_items"
        )
    )
    conn.execute(text("DROP TABLE watchlist_items"))
    conn.execute(text("ALTER TABLE watchlist_items_new RENAME TO watchlist_items"))
    conn.execute(text("CREATE INDEX ix_watchlist_items_symbol ON watchlist_items (symbol)"))
    conn.execute(text("CREATE INDEX ix_watchlist_items_user_id ON watchlist_items (user_id)"))
    conn.execute(text("PRAGMA foreign_keys=ON"))


def run(engine: Engine) -> None:
    with engine.begin() as conn:
        if not _has_table(conn, "users"):
            return  # banco novo: create_all já criou tudo no formato atual

        user_cols = _columns(conn, "users")
        legacy_users = "plan" not in user_cols
        for name, ddl in _USER_COLUMNS.items():
            if name not in user_cols:
                _add_column(conn, "users", name, ddl)
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_telegram_chat_id ON users (telegram_chat_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_stripe_customer_id ON users (stripe_customer_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_telegram_link_code ON users (telegram_link_code)"))

        if legacy_users:
            # Quem já usava o sistema antes dos planos continua com acesso completo.
            conn.execute(text("UPDATE users SET plan = 'pro'"))
            logger.info("Migração: usuários existentes mantidos no plano Pro.")

        for table in ("alert_logs", "transactions"):
            if _has_table(conn, table) and "user_id" not in _columns(conn, table):
                _add_column(conn, table, "user_id", "INTEGER REFERENCES users (id)")
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_user_id ON {table} (user_id)"))

        if _has_table(conn, "watchlist_items") and "user_id" not in _columns(conn, "watchlist_items"):
            if engine.dialect.name == "sqlite":
                _rebuild_watchlist_sqlite(conn)
            else:
                _add_column(conn, "watchlist_items", "user_id", "INTEGER REFERENCES users (id)")
                conn.execute(text("DROP INDEX IF EXISTS ix_watchlist_items_symbol"))
                conn.execute(text("CREATE INDEX ix_watchlist_items_symbol ON watchlist_items (symbol)"))
                conn.execute(text("CREATE INDEX ix_watchlist_items_user_id ON watchlist_items (user_id)"))
                conn.execute(
                    text(
                        "ALTER TABLE watchlist_items ADD CONSTRAINT uq_watchlist_user_symbol "
                        "UNIQUE (user_id, symbol)"
                    )
                )

        owner = conn.execute(
            text("SELECT id FROM users ORDER BY is_admin DESC, id ASC LIMIT 1")
        ).scalar()
        if owner is not None:
            for table in ("watchlist_items", "alert_logs", "transactions"):
                if _has_table(conn, table):
                    conn.execute(
                        text(f"UPDATE {table} SET user_id = :owner WHERE user_id IS NULL"), {"owner": owner}
                    )
            if settings.telegram_chat_id:
                conn.execute(
                    text(
                        "UPDATE users SET telegram_chat_id = :chat "
                        "WHERE id = :owner AND telegram_chat_id IS NULL"
                    ),
                    {"chat": str(settings.telegram_chat_id), "owner": owner},
                )
