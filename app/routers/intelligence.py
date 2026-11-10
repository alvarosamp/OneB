from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.bots import explanation_bot, score_bot
from app.data_quality import quality_gate, validate_symbol_data, validate_watchlist_data
from app.db import get_db
from app.intelligence import (
    DEFAULT_PLAYBOOKS,
    market_radar,
    movement_explanation,
    opportunity_score,
    signal_quality,
    weekly_brief,
)
from app.models import AlertCondition, AlertRule, DecisionJournal, Playbook, RuleLogic, RuleType, WatchlistItem
from app.saas import user_id_or_none
from app.schemas import DecisionJournalCreate, DecisionJournalOut, PlaybookCreate, PlaybookOut

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"], dependencies=[Depends(get_current_user)])


@router.get("/radar")
def radar(db: Session = Depends(get_db)):
    return market_radar(db)


@router.get("/score/{symbol}")
def score(symbol: str, db: Session = Depends(get_db)):
    return opportunity_score(db, symbol)


@router.get("/live-check/{symbol}")
def live_check(symbol: str, db: Session = Depends(get_db)):
    gate = quality_gate(db, symbol, min_confidence="MEDIUM")
    if not gate["allowed"]:
        return {"symbol": symbol.upper().strip(), "quality_gate": gate, "score_bot": "", "explanation_bot": ""}
    score_message = score_bot(db, symbol, refresh_real_data=True)
    explanation_message = explanation_bot(db, symbol, refresh_real_data=False)
    return {"symbol": symbol.upper().strip(), "quality_gate": gate, "score_bot": score_message.body, "explanation_bot": explanation_message.body}


@router.get("/data-quality")
def data_quality(db: Session = Depends(get_db)):
    return validate_watchlist_data(db)


@router.get("/data-quality/{symbol}")
def symbol_data_quality(symbol: str, db: Session = Depends(get_db)):
    return validate_symbol_data(db, symbol)


@router.get("/quality-gate/{symbol}")
def symbol_quality_gate(symbol: str, min_confidence: str = "MEDIUM", db: Session = Depends(get_db)):
    return quality_gate(db, symbol, min_confidence=min_confidence.upper())


@router.get("/explain/{symbol}")
def explain(symbol: str, db: Session = Depends(get_db)):
    return movement_explanation(db, symbol)


@router.get("/weekly-brief")
def brief(db: Session = Depends(get_db)):
    return weekly_brief(db)


@router.get("/signal-quality")
def quality(db: Session = Depends(get_db)):
    return signal_quality(db)


@router.get("/decisions", response_model=list[DecisionJournalOut])
def list_decisions(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return (
        db.query(DecisionJournal)
        .filter(DecisionJournal.user_id == user_id_or_none(user))
        .order_by(DecisionJournal.created_at.desc())
        .limit(100)
        .all()
    )


@router.post("/decisions", response_model=DecisionJournalOut, status_code=201)
def create_decision(payload: DecisionJournalCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    decision = DecisionJournal(
        user_id=user_id_or_none(user),
        symbol=payload.symbol.upper().strip(),
        thesis=payload.thesis,
        trigger=payload.trigger,
        invalidation=payload.invalidation,
        timeframe=payload.timeframe,
        risk_notes=payload.risk_notes,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return decision


@router.patch("/decisions/{decision_id}/{status}", response_model=DecisionJournalOut)
def update_decision_status(decision_id: int, status: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    decision = db.get(DecisionJournal, decision_id)
    if decision is None or decision.user_id != user_id_or_none(user):
        raise HTTPException(status_code=404, detail="Decisao nao encontrada")
    decision.status = status.upper()
    db.commit()
    db.refresh(decision)
    return decision


@router.get("/playbooks", response_model=list[PlaybookOut])
def list_playbooks(db: Session = Depends(get_db), user=Depends(get_current_user)):
    user_id = user_id_or_none(user)
    existing = db.query(Playbook).filter(Playbook.user_id == user_id).all()
    if existing:
        return existing
    playbooks = [Playbook(user_id=user_id, **payload) for payload in DEFAULT_PLAYBOOKS]
    db.add_all(playbooks)
    db.commit()
    return db.query(Playbook).filter(Playbook.user_id == user_id).all()


@router.post("/playbooks", response_model=PlaybookOut, status_code=201)
def create_playbook(payload: PlaybookCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    playbook = Playbook(
        user_id=user_id_or_none(user),
        name=payload.name,
        description=payload.description,
        rule_preset=payload.rule_preset,
    )
    db.add(playbook)
    db.commit()
    db.refresh(playbook)
    return playbook


@router.post("/playbooks/{playbook_id}/apply/{watchlist_item_id}")
def apply_playbook(playbook_id: int, watchlist_item_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    playbook = db.get(Playbook, playbook_id)
    item = db.get(WatchlistItem, watchlist_item_id)
    if playbook is None or item is None:
        raise HTTPException(status_code=404, detail="Playbook ou ativo nao encontrado")

    preset = playbook.rule_preset.upper()
    conditions = []
    if "VOLUME" in preset:
        conditions.append(AlertCondition(rule_type=RuleType.VOLUME_SPIKE, threshold=1.5, param_a=20))
    if "PRICE_ABOVE" in preset or "ROMPIMENTO" in preset or "BREAKOUT" in preset:
        conditions.append(AlertCondition(rule_type=RuleType.PCT_CHANGE, threshold=2.0, param_a=1))
    if "RSI" in preset or "PULLBACK" in preset:
        conditions.append(AlertCondition(rule_type=RuleType.RSI_OVERSOLD, threshold=40, param_a=14))
    if not conditions:
        conditions.append(AlertCondition(rule_type=RuleType.PCT_CHANGE, threshold=2.0, param_a=1))

    rule = AlertRule(watchlist_item_id=item.id, logic=RuleLogic.ANY, cooldown_minutes=240)
    rule.conditions = conditions
    db.add(rule)
    db.commit()
    return {"created_rule_id": rule.id, "symbol": item.symbol, "playbook": playbook.name}
