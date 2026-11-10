from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import billing
from app.copilot import analyze_symbol
from app.db import get_db
from app.models import User
from app.schemas import CopilotAnalyzeRequest

router = APIRouter(prefix="/api/copilot", tags=["copilot"])


@router.post("/analyze")
def analyze(
    payload: CopilotAnalyzeRequest, user: User = Depends(billing.require_pro), db: Session = Depends(get_db)
):
    return analyze_symbol(
        db,
        symbol=payload.symbol,
        capital_usd=payload.capital_usd,
        risk_budget_pct=payload.risk_budget_pct,
        question=payload.question,
        user_id=user.id,
    )
