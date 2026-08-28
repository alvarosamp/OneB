"""Export the raw timestamped news archive for future point-in-time research."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from app.db import SessionLocal
from app.models import NewsItem
from app.news_research import audit_news_rows
from app.research_provenance import write_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/research/news_archive_v1.csv"))
    parser.add_argument("--minimum-rows", type=int, default=500)
    args = parser.parse_args()
    db = SessionLocal()
    try:
        items = db.query(NewsItem).order_by(NewsItem.published_at.asc(), NewsItem.id.asc()).all()
        rows = [{"id": item.id, "symbol": item.symbol, "headline": item.headline, "summary": item.summary, "url": item.url, "source": item.source, "published_at": item.published_at, "fetched_at": item.fetched_at, "sentiment_score": item.sentiment_score} for item in items]
    finally:
        db.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.output, index=False)
    audit = audit_news_rows(rows, args.minimum_rows)
    audit_path = args.output.with_suffix(".audit.json")
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = write_manifest(args.output, command="python -m scripts.export_news_research_dataset", parameters={"minimum_rows": args.minimum_rows}, input_paths=["app/models.py", "app/news_research.py"], extra={"audit": audit, "audit_path": str(audit_path)})
    print(json.dumps({"dataset": str(args.output), "audit": audit, "manifest": str(manifest)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
