from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import reports, response_cache
from app.db import Base
from app.models import GlobalNewsItem, WatchlistItem


@pytest.fixture
def db():
    response_cache.clear()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        session.add(WatchlistItem(symbol="AAPL", label="Apple"))
        session.commit()
        yield session
    engine.dispose()
    response_cache.clear()


def history(price=100, *, days_old=0):
    dates = pd.date_range(end=datetime.now(timezone.utc) - timedelta(days=days_old), periods=80, freq="D")
    return pd.DataFrame({"open": price, "high": price + 1, "low": price - 1, "close": price, "volume": 1000}, index=dates)


def test_summary_fetches_new_prices_after_five_minutes(db, monkeypatch):
    clock = [0]
    monkeypatch.setattr(response_cache, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    provider = Mock(side_effect=[history(100), history(120)])
    monkeypatch.setattr(reports.market_data_service, "get_bars", provider)
    first = reports.build_daily_market_summary(db)
    clock[0] = 299
    cached = reports.build_daily_market_summary(db)
    assert provider.call_count == 1
    assert cached["data_checked_at"] == first["data_checked_at"]
    assert cached["generated_at"] >= first["generated_at"]
    clock[0] = 301
    fresh = reports.build_daily_market_summary(db)
    assert provider.call_count == 2
    rows = fresh["watch"] + fresh["risks"] + fresh["opportunities"]
    assert rows[0]["price"] == 120
    assert fresh["data_checked_at"] >= first["data_checked_at"]
    assert fresh["refresh_seconds"] == 300
    assert fresh["data_status"] == "complete"
    assert all(call.kwargs["refresh"] is True for call in provider.call_args_list)


def test_neutral_market_is_not_labelled_defensive(db, monkeypatch):
    monkeypatch.setattr(reports.market_data_service, "get_bars", lambda *a, **kw: history())
    row = reports._daily_asset_row(SimpleNamespace(symbol="AAPL", label="Apple"))
    row.update(score=50, bias="NEUTRO", volatility_label="Baixa")
    monkeypatch.setattr(reports, "_daily_asset_row", lambda item: row)
    assert reports.build_daily_market_summary(db)["market_tone"] == "Misto"


def test_saved_prices_keep_original_timestamp_and_warn(db, monkeypatch):
    old = datetime.now(timezone.utc) - timedelta(days=2)
    bars = history()
    bars.attrs.update(cache_fallback=True, fetched_at=old.isoformat())
    monkeypatch.setattr(reports.market_data_service, "get_bars", lambda *a, **kw: bars)
    summary = reports.build_daily_market_summary(db)
    assert summary["data_checked_at"] == old
    assert summary["data_status"] == "cached"
    assert any("fonte falhou" in note for note in summary["coverage_notes"])


def test_old_market_data_is_not_presented_as_current(db, monkeypatch):
    monkeypatch.setattr(reports.market_data_service, "get_bars", lambda *a, **kw: history(days_old=14))
    assert reports.build_daily_market_summary(db)["data_status"] == "stale"


def test_missing_coverage_and_old_news_are_explicit(db, monkeypatch):
    db.add(WatchlistItem(symbol="MISSING", label="No data"))
    db.add(GlobalNewsItem(headline="Old news", url="https://example.com/old", published_at=datetime.now(timezone.utc) - timedelta(days=5)))
    db.commit()
    monkeypatch.setattr(reports.market_data_service, "get_bars", lambda symbol, **kw: history() if symbol == "AAPL" else pd.DataFrame())
    summary = reports.build_daily_market_summary(db)
    assert summary["data_status"] == "partial"
    assert summary["analysed_count"] == 1
    assert summary["top_news"] == []
    assert any("MISSING" in note for note in summary["coverage_notes"])
    assert any("Calendário não carregado" in note for note in summary["coverage_notes"])
    assert any("Sem notícias coletadas" in note for note in summary["coverage_notes"])
