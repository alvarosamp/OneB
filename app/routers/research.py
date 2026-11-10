import re

import pandas as pd

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import WatchlistItem
from app.research import earnings, news_archive, risk_panel, service, signal_log, store

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


@router.get("/panel/{symbol}")
def panel(symbol: str, risk_pct: float = Query(1.0, gt=0, le=10), refresh: bool = False):
    """Painel de risco do ativo: regime, volatilidade, tamanho por risco, resultados e notícias."""
    symbol = symbol.upper().strip()
    if not _SYMBOL_RE.match(symbol):
        raise HTTPException(status_code=422, detail=f"Símbolo inválido: {symbol}")

    history = store.load(symbol)
    stale = history.empty or (pd.Timestamp.now().normalize() - history.index[-1]).days > 3
    if refresh or stale:
        history = store.update(symbol)
    if history.empty:
        raise HTTPException(status_code=404, detail=f"Sem histórico de preços para {symbol}")

    result = risk_panel.build(
        symbol,
        history,
        earnings_table=earnings.earnings_table(symbol),
        archive=news_archive.load(),
        risk_pct=risk_pct,
    )
    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])
    return result


@router.get("/signals")
def signals(limit: int = Query(30, ge=1, le=200)):
    """Registro de sinais em tempo real (paper trading) e o resultado dele contra comprar e segurar."""
    return signal_log.summary(limit)
