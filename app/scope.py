"""Consultas com escopo de usuário. `user_id=None` significa "todos" (jobs do agendador)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import PriceSnapshot, WatchlistItem


def active_watchlist(db: Session, user_id: int | None = None) -> list[WatchlistItem]:
    query = db.query(WatchlistItem).filter(WatchlistItem.active.is_(True))
    if user_id is not None:
        query = query.filter(WatchlistItem.user_id == user_id)
    return query.order_by(WatchlistItem.id).all()


def latest_snapshot(db: Session, item_id: int) -> PriceSnapshot | None:
    return (
        db.query(PriceSnapshot)
        .filter(PriceSnapshot.watchlist_item_id == item_id)
        .order_by(PriceSnapshot.taken_at.desc())
        .first()
    )


def latest_snapshot_for_symbol(db: Session, symbol: str) -> PriceSnapshot | None:
    """Cotação mais recente do símbolo em qualquer watchlist (o dado de mercado é compartilhado)."""
    return (
        db.query(PriceSnapshot)
        .join(WatchlistItem, PriceSnapshot.watchlist_item_id == WatchlistItem.id)
        .filter(WatchlistItem.symbol == symbol)
        .order_by(PriceSnapshot.taken_at.desc())
        .first()
    )
