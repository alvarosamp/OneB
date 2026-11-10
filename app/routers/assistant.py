from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.llm_client import answer_question
from app.models import AlertLog, GlobalNewsItem, NewsItem, PriceSnapshot, User, WatchlistItem
from app.schemas import AssistantAskRequest, AssistantAskResponse

router = APIRouter(prefix="/api/assistant", tags=["assistant"], dependencies=[Depends(get_current_user)])


def build_assistant_context(db: Session, user_id: int) -> dict:
    """Gathers a compact snapshot of what we already know, for the LLM to
    reason over. No external API calls — only what's already in our DB.
    """
    now = datetime.now(timezone.utc)

    items = (
        db.query(WatchlistItem)
        .filter(
            (WatchlistItem.user_id == user_id) | (WatchlistItem.user_id.is_(None)),
            WatchlistItem.active.is_(True),
        )
        .all()
    )
    watchlist = []
    for item in items:
        snap = (
            db.query(PriceSnapshot)
            .filter(PriceSnapshot.watchlist_item_id == item.id)
            .order_by(PriceSnapshot.taken_at.desc())
            .first()
        )
        watchlist.append(
            {
                "symbol": item.symbol,
                "label": item.label,
                "price": snap.price if snap else None,
                "change_pct": snap.change_pct if snap else None,
                "updated_at": snap.taken_at.isoformat() if snap else None,
            }
        )

    since = now - timedelta(hours=48)
    news = (
        db.query(NewsItem)
        .filter(NewsItem.published_at >= since)
        .order_by(NewsItem.published_at.desc())
        .limit(20)
        .all()
    )
    news_out = [{"symbol": n.symbol, "headline": n.headline, "published_at": n.published_at.isoformat()} for n in news]

    global_news = (
        db.query(GlobalNewsItem)
        .filter(GlobalNewsItem.published_at >= since)
        .order_by(GlobalNewsItem.impact_score.desc(), GlobalNewsItem.published_at.desc())
        .limit(12)
        .all()
    )
    global_news_out = [
        {
            "headline": n.headline,
            "source": n.source,
            "impact_score": n.impact_score,
            "published_at": n.published_at.isoformat(),
        }
        for n in global_news
    ]

    alerts = db.query(AlertLog).filter(AlertLog.user_id == user_id).order_by(AlertLog.triggered_at.desc()).limit(15).all()
    alerts_out = [{"symbol": a.symbol, "message": a.message, "triggered_at": a.triggered_at.isoformat()} for a in alerts]

    return {
        "watchlist": watchlist,
        "recent_news": news_out,
        "global_news": global_news_out,
        "recent_alerts": alerts_out,
    }


@router.post("/ask", response_model=AssistantAskResponse)
async def ask_assistant(payload: AssistantAskRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    context = build_assistant_context(db, user.id)
    history = [{"role": msg.role, "text": msg.text} for msg in payload.history[-8:]]
    answer = await answer_question(payload.question, context, history=history) if history else await answer_question(payload.question, context)
    return AssistantAskResponse(answer=answer)
