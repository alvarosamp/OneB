from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401  ensure models are registered

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_saas_columns()
    _ensure_sqlite_watchlist_symbol_scope()


def _ensure_sqlite_saas_columns():
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    additions = {
        "watchlist_items": {
            "user_id": "INTEGER",
            "workspace_id": "INTEGER",
            "asset_type": "VARCHAR(24) DEFAULT 'equity'",
        },
        "alert_logs": {
            "user_id": "INTEGER",
            "workspace_id": "INTEGER",
        },
        "transactions": {
            "user_id": "INTEGER",
        },
        "technical_levels": {
            "user_id": "INTEGER",
            "workspace_id": "INTEGER",
        },
        "trade_setups": {
            "user_id": "INTEGER",
            "workspace_id": "INTEGER",
        },
        "recommendation_decisions": {
            "user_id": "INTEGER",
            "workspace_id": "INTEGER",
            "horizon": "VARCHAR(16) DEFAULT '5d'",
            "direction": "VARCHAR(16) DEFAULT 'long'",
            "probability": "REAL",
            "uncertainty": "REAL",
            "regime": "VARCHAR(32) DEFAULT 'UNKNOWN'",
            "model_id": "VARCHAR(64) DEFAULT 'decision_engine'",
            "model_version": "VARCHAR(32) DEFAULT 'v1'",
            "dataset_version": "VARCHAR(64) DEFAULT 'live'",
            "quality_score": "REAL",
            "prediction_json": "TEXT DEFAULT '{}'",
            "data_as_of": "DATETIME",
            "outcome_return_1d_pct": "REAL",
            "outcome_return_20d_pct": "REAL",
            "outcome_1d_checked_at": "DATETIME",
            "outcome_20d_checked_at": "DATETIME",
        },
        "news_items": {
            "sentiment_score": "REAL",
        },
        "global_news_items": {
            "sentiment_score": "REAL",
        },
    }
    with engine.begin() as conn:
        for table, columns in additions.items():
            if table not in tables:
                continue
            for column_name, ddl in columns.items():
                inspector.clear_cache()
                existing = {column["name"] for column in inspector.get_columns(table)}
                if column_name not in existing:
                    try:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_name} {ddl}"))
                    except OperationalError as exc:
                        if "duplicate column name" not in str(exc).lower():
                            raise


def _ensure_sqlite_watchlist_symbol_scope():
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "watchlist_items" not in inspector.get_table_names():
        return

    with engine.begin() as conn:
        for index in inspector.get_indexes("watchlist_items"):
            if index.get("unique") and index.get("column_names") == ["symbol"]:
                conn.execute(text(f"DROP INDEX {index['name']}"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_watchlist_items_symbol ON watchlist_items (symbol)"))
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_watchlist_user_symbol "
                "ON watchlist_items (user_id, symbol)"
            )
        )
