from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AlertLog, PriceSnapshot, WatchlistItem
from app.reports import build_pdf_report


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_build_pdf_report_empty_watchlist_does_not_crash():
    db = _make_session()
    pdf_bytes = build_pdf_report(db, user_id=1)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_build_pdf_report_with_data():
    db = _make_session()
    item = WatchlistItem(symbol="AAPL", label="Apple")
    db.add(item)
    db.commit()
    db.add(PriceSnapshot(watchlist_item_id=item.id, price=150.0, change_pct=1.5, volume=1000))
    db.add(AlertLog(symbol="AAPL", rule_type="PRICE_ABOVE", message="AAPL passou de 150"))
    db.commit()

    pdf_bytes = build_pdf_report(db, user_id=1)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500
