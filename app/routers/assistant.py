from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import billing
from app.db import get_db
from app.llm_client import answer_question
from app.models import AlertLog, GlobalNewsItem, NewsItem, User
from app.scope import active_watchlist, latest_snapshot
from app.schemas import AssistantAskRequest, AssistantAskResponse

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


def build_assistant_context(db: Session, user_id: int | None = None) -> dict:
    """Gathers a compact snapshot of what we already know, for the LLM to
    reason over. No external API calls — only what's already in our DB.
    """
    now = datetime.now(timezone.utc)

    watchlist = []
    for item in active_watchlist(db, user_id):
        snap = latest_snapshot(db, item.id)
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

    alert_query = db.query(AlertLog)
    if user_id is not None:
        alert_query = alert_query.filter(AlertLog.user_id == user_id)
    alerts = alert_query.order_by(AlertLog.triggered_at.desc()).limit(15).all()
    alerts_out = [{"symbol": a.symbol, "message": a.message, "triggered_at": a.triggered_at.isoformat()} for a in alerts]

    return {
        "watchlist": watchlist,
        "recent_news": news_out,
        "global_news": global_news_out,
        "recent_alerts": alerts_out,
    }


@router.post("/ask", response_model=AssistantAskResponse)
async def ask_assistant(
    payload: AssistantAskRequest, user: User = Depends(billing.consume_llm_quota), db: Session = Depends(get_db)
):
    context = build_assistant_context(db, user.id)
    history = [{"role": msg.role, "text": msg.text} for msg in payload.history[-8:]]
    answer = await answer_question(payload.question, context, history=history) if history else await answer_question(payload.question, context)
    return AssistantAskResponse(answer=answer)
