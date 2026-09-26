from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import LiveSession, LiveStatus, User
from app.schemas import LiveSessionCreate, LiveSessionOut, LiveSessionStatusUpdate

router = APIRouter(prefix="/api/lives", tags=["lives"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[LiveSessionOut])
def list_lives(db: Session = Depends(get_db)):
    return db.query(LiveSession).order_by(LiveSession.scheduled_at.desc()).all()


@router.post("", response_model=LiveSessionOut, status_code=201)
def create_live(payload: LiveSessionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Apenas administradores podem agendar lives.")
    live = LiveSession(
        title=payload.title,
        description=payload.description,
        scheduled_at=payload.scheduled_at,
        stream_url=payload.stream_url,
    )
    db.add(live)
    db.commit()
    db.refresh(live)
    return live


@router.patch("/{live_id}/status", response_model=LiveSessionOut)
def update_live_status(
    live_id: int,
    payload: LiveSessionStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Apenas administradores podem atualizar a live.")
    live = db.query(LiveSession).filter(LiveSession.id == live_id).first()
    if live is None:
        raise HTTPException(status_code=404, detail="Live não encontrada.")
    try:
        live.status = LiveStatus(payload.status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Status inválido.") from None
    if payload.replay_url:
        live.replay_url = payload.replay_url
    db.commit()
    db.refresh(live)
    return live


def seed_default_lives(db: Session) -> None:
    if db.query(LiveSession).count() > 0:
        return
    now = datetime.now(timezone.utc)
    next_session = (now + timedelta(days=3)).replace(hour=13, minute=30, second=0, microsecond=0)
    db.add(
        LiveSession(
            title="Abertura de mercado NASDAQ",
            description="Leitura do pré-market, plano do dia e destaques da watchlist ao vivo.",
            status=LiveStatus.SCHEDULED,
            scheduled_at=next_session,
        )
    )
    db.add(
        LiveSession(
            title="Fechamento e revisão semanal",
            description="Replay da última sala de revisão de trades e setups da semana.",
            status=LiveStatus.ENDED,
            scheduled_at=now - timedelta(days=3),
            replay_url="",
        )
    )
    db.commit()
