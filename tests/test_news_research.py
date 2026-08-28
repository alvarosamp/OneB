from datetime import datetime, timezone

from app.news_research import audit_news_rows


def test_news_audit_marks_shallow_archive_as_warn():
    now = datetime.now(timezone.utc)
    report = audit_news_rows([{"symbol": "AAPL", "url": "https://example.test/a", "published_at": now, "fetched_at": now}], minimum_rows=2)
    assert report["status"] == "WARN"
    assert "INSUFFICIENT_ARCHIVE_DEPTH" in report["issues"]


def test_news_audit_detects_impossible_timestamp_order():
    now = datetime.now(timezone.utc)
    report = audit_news_rows([{"symbol": "AAPL", "url": "https://example.test/a", "published_at": now, "fetched_at": now.replace(year=2025)}], minimum_rows=1)
    assert "FETCH_BEFORE_PUBLISH_TIMESTAMP" in report["issues"]
