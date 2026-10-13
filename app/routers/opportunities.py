"""Oportunidades (ledger), evidência por setup, OneB AI v2 e feedback de paper trading."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.forward_stats import sample_size_note
from app.models import OpportunityEvent, PaperExecution, User
from app.oneb_ai import agent
from app.oneb_ai.tools import ToolContext, get_setup_stats
from app.opportunity import ACTIONABLE_APPROVALS, Approval
from app.opportunity_ledger import current_opportunities, diff_since, timeline, verify_chain
from app.reliability import assess_intraday_card

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"], dependencies=[Depends(get_current_user)])


def _setup_reliability(stats: dict, opportunity: dict) -> dict:
    """Reaproveita o índice intradiário com a evidência do replay/forward do setup."""
    summary = stats.get("summary") or {}
    data = stats.get("data") or {}
    return assess_intraday_card({
        "action": "NO_TRADE" if opportunity["approval"] not in {a.value for a in ACTIONABLE_APPROVALS} else "CANDIDATE",
        "approval": opportunity["approval"],
        "data_health": {"sessions": data.get("sessions") or 0, "fresh": True,
                        "clock_verified": data.get("clock") == "VERIFIED"},
        "holdout_evidence": {"trades": summary.get("completed_trades"), "profit_factor": summary.get("profit_factor"),
                             "bh_q_value": None},
    })


@router.get("")
def list_opportunities(symbol: str | None = None, mode: str | None = None, db: Session = Depends(get_db)):
    ctx = ToolContext(db=db)
    opportunities = current_opportunities(db, symbol=symbol, mode=mode)
    stats_cache: dict[str, dict] = {}
    for opp in opportunities:
        setup_key = f"{opp['setup']}_v1"
        if setup_key not in stats_cache:
            stats_cache[setup_key] = get_setup_stats(ctx, setup_key)
        stats = stats_cache[setup_key]
        opp["setup_evidence"] = {"verdict": stats.get("verdict"), "summary": stats.get("summary")} if stats.get("summary") else None
        opp["reliability"] = _setup_reliability(stats, opp) if stats.get("summary") else None
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "opportunities": opportunities}


@router.get("/timeline")
def opportunity_timeline(opportunity_id: str | None = None, symbol: str | None = None, since_minutes: int | None = None,
                         db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(minutes=since_minutes) if since_minutes else None
    return {"events": timeline(db, opportunity_id=opportunity_id, symbol=symbol, since=since)}


@router.get("/changes")
def opportunity_changes(since_minutes: int = 30, symbol: str | None = None, db: Session = Depends(get_db)):
    return diff_since(db, datetime.now(timezone.utc) - timedelta(minutes=max(1, min(since_minutes, 7 * 24 * 60))), symbol=symbol)


@router.get("/setups/{setup}/evidence")
def setup_evidence(setup: str, db: Session = Depends(get_db)):
    stats = get_setup_stats(ToolContext(db=db), setup)
    if stats.get("status") == "UNAVAILABLE":
        raise HTTPException(status_code=404, detail=stats["reason"])
    stats["sample_size"] = stats.get("sample_size") or sample_size_note(stats["summary"])
    return stats


@router.get("/ledger/verify")
def ledger_verify(mode: str = "SHADOW", db: Session = Depends(get_db)):
    return verify_chain(db, mode)


class OneBAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list)


@router.post("/ai/ask")
async def oneb_ai_ask(payload: OneBAskRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return await agent.ask(ToolContext(db=db, user_id=user.id), payload.question, history=payload.history)


class PaperFeedback(BaseModel):
    decision: str = Field(pattern="^(OPERATED|SKIPPED|DIFFERENT)$")
    executed_price: float | None = Field(default=None, gt=0)
    exit_price: float | None = Field(default=None, gt=0)
    executed_at: datetime | None = None
    notes: str = Field(default="", max_length=2000)


@router.post("/{opportunity_id:path}/paper", status_code=201)
def paper_feedback(opportunity_id: str, payload: PaperFeedback, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    events = db.query(OpportunityEvent).filter(OpportunityEvent.opportunity_id == opportunity_id).order_by(OpportunityEvent.id).all()
    if not events:
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada.")
    if Approval(events[-1].approval) not in ACTIONABLE_APPROVALS:
        raise HTTPException(status_code=409, detail="Setup ainda não aprovado para paper trading; feedback não é registrado.")
    planned = next((float(e.payload["entry"]) for e in reversed(events) if "entry" in (e.payload or {})), None)
    if planned is None:
        planned = next((float(e.payload["reference_close"]) for e in reversed(events) if "reference_close" in (e.payload or {})), None)
    direction = events[-1].direction
    slippage = None
    if payload.executed_price is not None and planned is not None:
        side = 1 if direction == "long" else -1
        slippage = round(side * (payload.executed_price - planned), 5)  # positivo = pior que o plano
    row = PaperExecution(user_id=user.id, opportunity_id=opportunity_id, decision=payload.decision, planned_entry=planned,
                         executed_price=payload.executed_price, exit_price=payload.exit_price, direction=direction,
                         slippage=slippage, notes=payload.notes, executed_at=payload.executed_at)
    db.add(row)
    db.commit()
    return {"id": row.id, "slippage": slippage, "planned_entry": planned}


@router.get("/paper/summary")
def paper_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(PaperExecution).filter(PaperExecution.user_id == user.id).all()
    slips = [r.slippage for r in rows if r.slippage is not None]
    return {
        "records": len(rows),
        "operated": sum(r.decision == "OPERATED" for r in rows),
        "skipped": sum(r.decision == "SKIPPED" for r in rows),
        "avg_human_slippage": round(sum(slips) / len(slips), 5) if slips else None,
        "note": "Slippage humano positivo = execução pior que o plano; entra como custo no simulador.",
    }
