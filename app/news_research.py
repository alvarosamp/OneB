"""Point-in-time export and quality checks for the growing news archive."""
from __future__ import annotations

from datetime import datetime, timezone


def audit_news_rows(rows: list[dict], minimum_rows: int = 500) -> dict:
    """Audit records without fitting sentiment or leaking future information."""
    urls = [row.get("url") for row in rows if row.get("url")]
    published = [row.get("published_at") for row in rows if row.get("published_at")]
    fetched = [row.get("fetched_at") for row in rows if row.get("fetched_at")]
    late = sum(1 for row in rows if row.get("published_at") and row.get("fetched_at") and row["fetched_at"] < row["published_at"])
    issues = []
    if len(rows) < minimum_rows:
        issues.append("INSUFFICIENT_ARCHIVE_DEPTH")
    if len(set(urls)) != len(urls):
        issues.append("DUPLICATE_URLS")
    if late:
        issues.append("FETCH_BEFORE_PUBLISH_TIMESTAMP")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(), "rows": len(rows), "unique_urls": len(set(urls)),
        "symbols": len({row.get("symbol") for row in rows if row.get("symbol")}), "published_start": min(published).isoformat() if published else None,
        "published_end": max(published).isoformat() if published else None, "latest_fetched_at": max(fetched).isoformat() if fetched else None,
        "invalid_timestamp_order_rows": late, "minimum_rows": minimum_rows, "status": "PASS" if not issues else "WARN", "issues": issues,
    }
