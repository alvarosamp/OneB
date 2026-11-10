import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import billing
from app.auth import get_current_user
from app.backtest import backtest_conditions
from app.db import get_db
from app.market_data import yfinance_client
from app.models import AlertCondition, AlertRule, User, WatchlistItem
from app.rules_engine import RuleContext
from app.scope import active_watchlist
from app.schemas import (
    AlertRuleCreate,
    AlertRuleOut,
    BacktestRequest,
    BacktestResponse,
    WatchlistItemCreate,
    WatchlistItemOut,
)

_SYMBOL_RE = re.compile(r"^[A-Z0-9^=.\-]{1,16}$")

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


def _own_item(db: Session, user: User, item_id: int) -> WatchlistItem:
    item = db.get(WatchlistItem, item_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Ativo não encontrado")
    return item


@router.get("", response_model=list[WatchlistItemOut])
def list_watchlist(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return active_watchlist(db, user.id)


@router.post("", response_model=WatchlistItemOut, status_code=201)
def create_watchlist_item(
    payload: WatchlistItemCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    symbol = payload.symbol.upper().strip()
    if not _SYMBOL_RE.match(symbol):
        raise HTTPException(status_code=422, detail="Símbolo inválido")
    billing.check_symbol_quota(db, user, symbol)
    existing = (
        db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id, WatchlistItem.symbol == symbol).first()
    )
    if existing:
        existing.active = True
        existing.label = payload.label or existing.label
        db.commit()
        db.refresh(existing)
        return existing

    item = WatchlistItem(user_id=user.id, symbol=symbol, label=payload.label)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def deactivate_watchlist_item(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _own_item(db, user, item_id)
    item.active = False
    db.commit()


@router.post("/{item_id}/rules", response_model=AlertRuleOut, status_code=201)
def create_rule(
    item_id: int,
    payload: AlertRuleCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _own_item(db, user, item_id)
    if not payload.conditions:
        raise HTTPException(status_code=400, detail="A regra precisa de pelo menos uma condição")
    billing.check_rule_quota(db, user)

    rule = AlertRule(watchlist_item_id=item_id, logic=payload.logic, cooldown_minutes=payload.cooldown_minutes)
    rule.conditions = [
        AlertCondition(
            rule_type=cond.rule_type,
            threshold=cond.threshold,
            param_a=cond.param_a,
            param_b=cond.param_b,
        )
        for cond in payload.conditions
    ]
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/{item_id}/rules", response_model=list[AlertRuleOut])
def list_rules(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _own_item(db, user, item_id)
    return db.query(AlertRule).filter(AlertRule.watchlist_item_id == item_id).all()


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rule = db.get(AlertRule, rule_id)
    if not rule or rule.watchlist_item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    rule.active = False
    db.commit()


@router.post("/rules/backtest", response_model=BacktestResponse)
def backtest_rule(
    payload: BacktestRequest, user: User = Depends(billing.rate_limit("backtest", 20, 60))
):
    history = yfinance_client.get_history(
        payload.symbol.upper(), period=payload.period, interval=payload.interval
    )
    if history.empty:
        raise HTTPException(status_code=404, detail="Sem dados históricos para este símbolo")

    conditions = [
        RuleContext(rule_type=c.rule_type, threshold=c.threshold, param_a=c.param_a, param_b=c.param_b)
        for c in payload.conditions
    ]
    result = backtest_conditions(
        conditions, payload.logic, history, symbol=payload.symbol.upper(), forward_bars=payload.forward_bars
    )
    return result
