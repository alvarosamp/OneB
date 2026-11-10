from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import probability_model as pm
from app.auth import get_current_user
from app.db import get_db
from app.decision_engine import (
    build_decision_desk,
    build_decision_health,
    build_market_divergence,
    build_reliability_scoreboard,
    latest_decisions,
)
from app.schemas import (
    DecisionDeskOut,
    MarketDivergenceOut,
    ModelHealthOut,
    RecommendationDecisionOut,
    ReliabilityScoreboardOut,
)

router = APIRouter(prefix="/api/decision-desk", tags=["decision-desk"], dependencies=[Depends(get_current_user)])


@router.get("/recommendations", response_model=DecisionDeskOut)
async def recommendations(record: bool = False, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return await build_decision_desk(db, user, record=record)


@router.get("/history", response_model=list[RecommendationDecisionOut])
def history(limit: int = 50, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return latest_decisions(db, user, limit=max(1, min(limit, 200)))


@router.get("/scoreboard", response_model=ReliabilityScoreboardOut)
def scoreboard(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return build_reliability_scoreboard(db, user)


@router.get("/model-health", response_model=ModelHealthOut)
def model_health():
    return pm.health()


@router.get("/decision-health")
def decision_health(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return build_decision_health(db, user)


@router.get("/market-divergence", response_model=MarketDivergenceOut)
def market_divergence(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return build_market_divergence(db, user)
