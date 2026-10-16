import asyncio
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import scheduler
from app.db import Base
from app.market_data.fred_client import EconomicEventEntry
from app.models import EconomicEvent


def test_refresh_calendars_does_not_duplicate_naive_sqlite_dates(monkeypatch):
    """SQLite devolve a data sem fuso e o FRED com fuso: o mesmo evento não pode parecer novo (antes, o job inteiro caía)."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(EconomicEvent(event_name="FOMC Rate Decision", country="US", event_date=datetime(2026, 10, 28, 18, 0), impact="high"))
    db.commit()
    db.close()
    when = datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)
    cpi = datetime(2026, 11, 10, 13, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(scheduler, "SessionLocal", Session)
    monkeypatch.setattr(scheduler, "purge_legacy_economic_events", lambda db: 0)
    monkeypatch.setattr(scheduler.fred_client, "get_economic_calendar", lambda a, b: [
        EconomicEventEntry(event_name="FOMC Rate Decision", country="US", event_date=when, impact="high", actual="", forecast="", previous=""),
        EconomicEventEntry(event_name="Consumer Price Index (CPI)", country="US", event_date=cpi, impact="high", actual="", forecast="", previous=""),
    ])
    asyncio.run(scheduler.refresh_calendars())
    db = Session()
    names = sorted(e.event_name for e in db.query(EconomicEvent).all())
    db.close()
    engine.dispose()
    assert names == ["Consumer Price Index (CPI)", "FOMC Rate Decision"]
