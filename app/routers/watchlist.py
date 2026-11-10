from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import audit
from app.auth import get_current_user
from app.backtest import backtest_conditions
from app.db import get_db
from app.market_data import service as market_data_service
from app.models import AlertCondition, AlertRule, PriceSnapshot, User, WatchlistItem
from app.rules_engine import RuleContext
from app.saas import ensure_limit, get_or_create_workspace
from app.schemas import (
    AlertRuleCreate,
    AlertRuleOut,
    BacktestRequest,
    BacktestResponse,
    WatchlistItemCreate,
    WatchlistItemOut,
    WatchlistPriceOut,
)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"], dependencies=[Depends(get_current_user)])


def _infer_asset_type(symbol: str, explicit: str = "") -> str:
    value = explicit.lower().strip()
    allowed = {"equity", "etf", "index", "commodity", "fx", "bond_yield", "macro"}
    if value in allowed:
        return value
    upper = symbol.upper()
    if upper in {"GOLD", "GC=F", "SI=F", "CL=F", "BZ=F"}:
        return "commodity"
    if upper.endswith("=X") or upper in {"EURUSD", "EURBRL", "USDBRL"}:
        return "fx"
    if upper in {"NASDAQ", "SP500", "^NDX", "^GSPC", "NQ=F", "ES=F"}:
        return "index"
    if upper in {"DXY", "VIX", "US2Y", "US5Y", "US10Y", "US30Y"}:
        return "macro"
    if upper in {"QQQ", "SPY", "GLD", "SLV", "TLT", "HYG"}:
        return "etf"
    return "equity"


def _can_manage_item(item: WatchlistItem, user: User, workspace_id: int | None) -> bool:
    return (
        getattr(user, "is_admin", False)
        or item.user_id in (None, getattr(user, "id", None))
        or item.workspace_id in (None, workspace_id)
    )


@router.get("", response_model=list[WatchlistItemOut])
def list_watchlist(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # WatchlistItem.symbol is unique table-wide (one shared row per symbol,
    # not per workspace — see the comment in create_watchlist_item), so this
    # has to list every active item regardless of workspace_id to match:
    # every other reader (decision_engine, paper_simulator, reports,
    # morning_report, assistant) already treats the watchlist as one global
    # list. Scoping this one endpoint by workspace made symbols invisible to
    # whichever workspace didn't happen to create them first.
    workspace = get_or_create_workspace(db, user)
    items = db.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).all()
    return [item for item in items if _can_manage_item(item, user, workspace.id)]


@router.get("/prices", response_model=list[WatchlistPriceOut])
def list_watchlist_prices(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace = get_or_create_workspace(db, user)
    items = db.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).all()
    items = [item for item in items if _can_manage_item(item, user, workspace.id)]

    rows = []
    for item in items:
        snap = (
            db.query(PriceSnapshot)
            .filter(PriceSnapshot.watchlist_item_id == item.id)
            .order_by(PriceSnapshot.taken_at.desc())
            .first()
        )
        rows.append(
            WatchlistPriceOut(
                id=item.id,
                symbol=item.symbol,
                label=item.label,
                asset_type=item.asset_type or "equity",
                price=snap.price if snap else None,
                change_pct=snap.change_pct if snap else None,
                taken_at=snap.taken_at if snap else None,
            )
        )
    return rows


@router.post("", response_model=WatchlistItemOut, status_code=201)
def create_watchlist_item(payload: WatchlistItemCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    symbol = payload.symbol.upper().strip()
    asset_type = _infer_asset_type(symbol, payload.asset_type)
    workspace = get_or_create_workspace(db, user)
    # WatchlistItem.symbol has a table-wide unique constraint (one shared row
    # per symbol across every workspace) — the lookup has to match that, not
    # just the current workspace, or a symbol already owned by a different
    # workspace fails the INSERT with a raw IntegrityError instead of being
    # reactivated/shared here.
    existing = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.symbol == symbol)
        .filter((WatchlistItem.user_id == getattr(user, "id", None)) | (WatchlistItem.workspace_id == workspace.id))
        .first()
    )
    if existing is None:
        existing = (
            db.query(WatchlistItem)
            .filter(WatchlistItem.symbol == symbol, WatchlistItem.user_id.is_(None), WatchlistItem.workspace_id.is_(None))
            .first()
        )
    if existing:
        existing.active = True
        existing.user_id = existing.user_id or getattr(user, "id", None)
        existing.workspace_id = existing.workspace_id or workspace.id
        existing.label = payload.label or existing.label
        existing.asset_type = asset_type or existing.asset_type
        audit(db, user, "watchlist.reactivate", "watchlist_item", existing.id, {"symbol": symbol})
        db.commit()
        db.refresh(existing)
        return existing

    ensure_limit(db, workspace, "watchlist_items")
    item = WatchlistItem(
        symbol=symbol,
        label=payload.label,
        asset_type=asset_type,
        user_id=getattr(user, "id", None),
        workspace_id=workspace.id,
    )
    db.add(item)
    audit(db, user, "watchlist.create", "watchlist_item", symbol, {"symbol": symbol})
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def deactivate_watchlist_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.get(WatchlistItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Ativo não encontrado")
    workspace = get_or_create_workspace(db, user)
    if not _can_manage_item(item, user, workspace.id):
        raise HTTPException(status_code=404, detail="Ativo nao encontrado")
    item.active = False
    audit(db, user, "watchlist.deactivate", "watchlist_item", item.id, {"symbol": item.symbol})
    db.commit()


@router.post("/{item_id}/rules", response_model=AlertRuleOut, status_code=201)
def create_rule(item_id: int, payload: AlertRuleCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.get(WatchlistItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Ativo não encontrado")
    if not payload.conditions:
        raise HTTPException(status_code=400, detail="A regra precisa de pelo menos uma condição")

    workspace = get_or_create_workspace(db, user)
    if not _can_manage_item(item, user, workspace.id):
        raise HTTPException(status_code=404, detail="Ativo nao encontrado")
    ensure_limit(db, workspace, "alert_rules")
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
    audit(db, user, "rule.create", "alert_rule", item_id, {"symbol": item.symbol})
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/{item_id}/rules", response_model=list[AlertRuleOut])
def list_rules(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.get(WatchlistItem, item_id)
    workspace = get_or_create_workspace(db, user)
    if not item or not _can_manage_item(item, user, workspace.id):
        raise HTTPException(status_code=404, detail="Ativo não encontrado")
    return db.query(AlertRule).filter(AlertRule.watchlist_item_id == item_id).all()


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rule = (
        db.query(AlertRule)
        .join(WatchlistItem, AlertRule.watchlist_item_id == WatchlistItem.id)
        .filter(AlertRule.id == rule_id)
        .first()
    )
    workspace = get_or_create_workspace(db, user)
    if not rule or not _can_manage_item(rule.watchlist_item, user, workspace.id):
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    rule.active = False
    db.commit()


@router.post("/rules/backtest", response_model=BacktestResponse)
def backtest_rule(payload: BacktestRequest):
    history = market_data_service.get_bars(payload.symbol.upper(), period=payload.period, interval=payload.interval)
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
