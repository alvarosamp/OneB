import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import WatchlistItem
from app.research import service

router = APIRouter(prefix="/api/research", tags=["research"], dependencies=[Depends(get_current_user)])

BENCHMARKS = ["QQQ", "SPY", "GC=F"]
MAX_SYMBOLS = 15
_SYMBOL_RE = re.compile(r"^[A-Z0-9^=.\-]{1,16}$")


@router.get("/study")
def study(
    symbols: str = Query("", description="Tickers separados por vírgula; vazio = watchlist + QQQ/SPY/ouro"),
    refresh: bool = False,
    db: Session = Depends(get_db),
):
    """Estudo de correlações, regimes e eventos. `refresh=true` busca dados novos (mais lento)."""
    if symbols.strip():
        chosen = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    else:
        watch = db.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).all()
        chosen = [w.symbol for w in watch] + BENCHMARKS

    chosen = list(dict.fromkeys(chosen))
    bad = [s for s in chosen if not _SYMBOL_RE.match(s)]
    if bad:
        raise HTTPException(status_code=422, detail=f"Símbolo inválido: {', '.join(bad)}")
    if len(chosen) > MAX_SYMBOLS:
        raise HTTPException(status_code=422, detail=f"Máximo de {MAX_SYMBOLS} ativos por estudo")

    return service.run_study(chosen, refresh=refresh)
