"""Endpoints sem login: só o registro de sinais agregado (nada de dados de usuários)."""
from fastapi import APIRouter, Query

from app.research import signal_log

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/track-record")
def track_record(limit: int = Query(30, ge=1, le=100)):
    """Placar público e auditável da regra de tendência contra comprar e segurar."""
    return signal_log.summary(limit)
