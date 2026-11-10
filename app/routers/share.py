from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import audit
from app.auth import get_current_user
from app.db import get_db
from app.models import PriceSnapshot, ShareLink, WatchlistItem
from app.saas import get_or_create_workspace

router = APIRouter(prefix="/api/share", tags=["share"])


@router.post("/watchlist")
def create_watchlist_share(db: Session = Depends(get_db), user=Depends(get_current_user)):
    workspace = get_or_create_workspace(db, user)
    link = ShareLink(workspace_id=workspace.id, slug=secrets.token_urlsafe(10), title=f"{workspace.brand_name} - Watchlist")
    db.add(link)
    audit(db, user, "share.create", "share_link", link.slug, {"scope": "watchlist"})
    db.commit()
    db.refresh(link)
    return {"slug": link.slug, "url_path": f"/share/{link.slug}", "title": link.title}


@router.get("/{slug}")
def public_watchlist(slug: str, db: Session = Depends(get_db)):
    link = db.query(ShareLink).filter(ShareLink.slug == slug, ShareLink.active.is_(True)).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Link nao encontrado")
    items = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.active.is_(True))
        .filter((WatchlistItem.workspace_id == link.workspace_id) | (WatchlistItem.workspace_id.is_(None)))
        .all()
    )
    rows = []
    for item in items:
        snap = (
            db.query(PriceSnapshot)
            .filter(PriceSnapshot.watchlist_item_id == item.id)
            .order_by(PriceSnapshot.taken_at.desc())
            .first()
        )
        rows.append(
            {
                "symbol": item.symbol,
                "label": item.label,
                "price": snap.price if snap else None,
                "change_pct": snap.change_pct if snap else None,
                "taken_at": snap.taken_at.isoformat() if snap else None,
            }
        )
    return {"title": link.title, "rows": rows}
