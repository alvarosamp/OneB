from datetime import date, datetime, timezone

from app.market_data import fomc_schedule, fred_client


class _Resp:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_calendar_uses_future_dates_release_time_and_official_fomc(monkeypatch):
    seen = {}

    def fake_get(url, params, timeout):
        seen.update(params)
        # 101 aparece todo dia no FRED: não pode virar FOMC.
        return _Resp({"release_dates": [{"release_id": 101, "date": "2026-10-12"}, {"release_id": 10, "date": "2026-10-14"},
                                        {"release_id": 50, "date": "2026-11-06"}]})

    monkeypatch.setattr(fred_client.settings, "fred_api_key", "x")
    monkeypatch.setattr(fred_client.httpx, "get", fake_get)
    events = fred_client.get_economic_calendar(date(2026, 10, 10), date(2026, 11, 10))
    assert seen["include_release_dates_with_no_data"] == "true"
    got = [(e.event_name, e.event_date) for e in events]
    assert ("Consumer Price Index (CPI)", datetime(2026, 10, 14, 12, 30, tzinfo=timezone.utc)) in got  # 08:30 EDT
    assert ("Employment Situation (NFP)", datetime(2026, 11, 6, 13, 30, tzinfo=timezone.utc)) in got  # 08:30 EST
    assert ("FOMC Rate Decision", datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)) in got
    assert not any(n == "FOMC Press Release" for n, _ in got)


def test_fomc_schedule_in_range():
    assert [d.date() for d in fomc_schedule.decisions_between(date(2026, 10, 1), date(2026, 12, 31))] == [date(2026, 10, 28), date(2026, 12, 9)]


def test_purge_removes_fake_fomc_and_midnight_rows():
    from app.db import SessionLocal
    from app.models import EconomicEvent
    from app.scheduler import purge_legacy_economic_events

    db = SessionLocal()
    try:
        rows = [
            EconomicEvent(event_name="FOMC Press Release", country="US", event_date=datetime(2026, 10, 10, tzinfo=timezone.utc), impact="high"),
            EconomicEvent(event_name="Consumer Price Index (CPI)", country="US", event_date=datetime(2026, 10, 14, tzinfo=timezone.utc), impact="high"),
            EconomicEvent(event_name="Consumer Price Index (CPI)", country="US", event_date=datetime(2026, 10, 14, 12, 30, tzinfo=timezone.utc), impact="high"),
        ]
        db.add_all(rows)
        db.flush()
        assert purge_legacy_economic_events(db) == 2
        left = db.query(EconomicEvent).filter(EconomicEvent.event_name.in_(["FOMC Press Release", "Consumer Price Index (CPI)"])).all()
        assert [(e.event_name, e.event_date.hour) for e in left] == [("Consumer Price Index (CPI)", 12)]
    finally:
        db.rollback()
        db.close()
