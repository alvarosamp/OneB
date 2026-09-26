from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, _connection_record):
        """API, worker e paper-simulator escrevem no MESMO arquivo SQLite.

        WAL deixa leitura e escrita concorrerem (em vez de a leitura bloquear
        a escrita) e busy_timeout faz um writer esperar o lock em vez de
        estourar SQLITE_BUSY na hora. Isso NAO transforma SQLite em banco
        multi-writer -- continua havendo um writer por vez, e WAL nao funciona
        com o arquivo num filesystem de rede. E mitigacao, nao solucao: a saida
        de verdade para escala horizontal e PostgreSQL.
        foreign_keys=ON porque o SQLite ignora FKs por padrao.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Prepara o schema no boot.

    Em SQLite (dev e testes) o schema e criado direto a partir dos modelos, junto com os
    ajustes incrementais abaixo -- e o caminho que faz `docker compose up` funcionar sem
    nenhum passo extra. Em qualquer outro banco (PostgreSQL em producao) o schema e
    responsabilidade das migrations do Alembic (`alembic upgrade head`, rodado pelo
    servico `migrate` do docker-compose.prod.yml): criar tabelas por create_all ali
    deixaria o banco fora do controle de versao do schema.
    """
    from app import models  # noqa: F401  ensure models are registered

    if not settings.database_url.startswith("sqlite"):
        return

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
