from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import regime_engine
from app.auth import get_current_user
from app.db import get_db
from app.market_data import macro_data

router = APIRouter(prefix="/api/regime", tags=["regime"], dependencies=[Depends(get_current_user)])


@router.get("/macro")
def macro_overview(db: Session = Depends(get_db)):
    """Latest quote + cross-asset relevance table for every tracked macro
    instrument — the Level 2 (macro regime) read for the platform.
    """
    instruments = []
    histories = regime_engine.collect_macro_histories(refresh=False)
    for key, (_source, symbol, name) in macro_data.MACRO_INSTRUMENTS.items():
        snapshot = regime_engine.latest_macro_snapshot(db, key)
        history = histories[key]
        instruments.append(
            {
                "key": key,
                "symbol": symbol,
                "name": name,
                "price": snapshot.price if snapshot else None,
                "change_pct": snapshot.change_pct if snapshot else None,
                "taken_at": snapshot.taken_at.isoformat() if snapshot else None,
                "trend": regime_engine.trend_analysis(history, yield_series=key.startswith("US") and key.endswith("Y")),
                "context": macro_data.TREND_CONTEXT.get(key),
            }
        )
    by_key = {row["key"]: row for row in instruments}
    correlation_windows = regime_engine.macro_correlation_analysis(histories)
    persisted_history = regime_engine.macro_intelligence_history(db, limit=365)
    latest_row = persisted_history["snapshots"][0] if persisted_history["snapshots"] else None
    latest_persisted = (
        {key: value for key, value in latest_row.items() if key != "payload"}
        if latest_row
        else None
    )
    return {
        "instruments": instruments,
        "trend_watchlist": [by_key[key] for key in macro_data.TREND_WATCHLIST if key in by_key],
        "correlation_windows": correlation_windows,
        "relationship_dynamics": regime_engine.macro_relationship_dynamics(correlation_windows),
        "lead_lag_candidates": regime_engine.macro_lead_lag_candidates(histories),
        "history_status": {
            "days_recorded": persisted_history["days_recorded"],
            "latest": latest_persisted,
            "lead_lag_validation": persisted_history["lead_lag_validation"][:10],
            "latest_news_context": (latest_row.get("payload") or {}).get("news_context") if latest_row else None,
            "news_market_analysis": persisted_history["news_market_analysis"],
        },
        "nasdaq_cross_asset_relevance": regime_engine.cross_asset_relevance(db, target_key="NASDAQ"),
    }


@router.get("/macro/history")
def macro_history(limit: int = Query(default=365, ge=1, le=365), db: Session = Depends(get_db)):
    """Daily persisted cross-asset states used to validate stability over time."""
    return regime_engine.macro_intelligence_history(db, limit=limit)


@router.get("/{symbol}")
def symbol_regime(symbol: str, db: Session = Depends(get_db)):
    """Local regime (trend/momentum/volatility/structure) for `symbol`,
    plus the macro overlay relevant to it. `symbol` accepts an equity
    ticker or a MACRO_INSTRUMENTS key (NASDAQ, SP500, GOLD, DXY, ...).
    """
    report = regime_engine.regime_report(db, symbol)
    if report["local_regime"] is None and not report["cross_asset_relevance"]:
        raise HTTPException(status_code=404, detail="Sem historico suficiente para calcular o regime deste ativo.")
    return report
