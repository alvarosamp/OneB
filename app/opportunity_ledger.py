"""Ledger append-only de oportunidades + leituras derivadas (estado atual, timeline, diff).

O "Copiloto Temporal" é calculado aqui, em Python: o que mudou entre dois
instantes é um diff de eventos do ledger. A LLM só narra esse diff.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import OpportunityEvent
from app.opportunity import (
    TERMINAL_STATES,
    Approval,
    EvidenceItem,
    Levels,
    Opportunity,
    SetupState,
    Transition,
    canonical_json,
    parse_time,
    sha256_text,
)

MODES = {"REPLAY", "SHADOW", "LIVE"}


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _event_hash(body: dict, prev_hash: str | None) -> str:
    return sha256_text(canonical_json({"body": body, "prev": prev_hash}))


def _body(event: OpportunityEvent) -> dict:
    return {
        "opportunity_id": event.opportunity_id, "setup": event.setup, "setup_version": event.setup_version,
        "symbol": event.symbol, "mode": event.mode, "state": event.state, "from_state": event.from_state,
        "direction": event.direction, "approval": event.approval, "reason": event.reason,
        "payload": event.payload, "event_at": _utc(event.event_at).isoformat(),
    }


def record_transition(
    db: Session,
    transition: Transition,
    *,
    setup: str,
    setup_version: str,
    symbol: str,
    mode: str,
    approval: Approval,
    commit: bool = True,
) -> OpportunityEvent:
    if mode not in MODES:
        raise ValueError(f"modo inválido: {mode}")
    opportunity_id = transition.payload.get("opportunity_id")
    if not opportunity_id:
        raise ValueError("transição sem opportunity_id")
    last = db.query(OpportunityEvent).filter(OpportunityEvent.mode == mode).order_by(OpportunityEvent.id.desc()).first()
    event = OpportunityEvent(
        opportunity_id=opportunity_id, setup=setup, setup_version=setup_version, symbol=symbol, mode=mode,
        state=transition.to_state.value, from_state=transition.from_state.value, direction=transition.direction,
        approval=approval.value, reason=transition.reason, payload=transition.payload,
        event_at=_utc(parse_time(transition.at)), prev_hash=last.hash if last else None,
    )
    event.hash = _event_hash(_body(event), event.prev_hash)
    db.add(event)
    if commit:
        db.commit()
        db.refresh(event)
    else:
        db.flush()
    return event


def verify_chain(db: Session, mode: str) -> dict:
    """Recalcula a cadeia; qualquer edição/remoção em linha antiga aparece aqui."""
    prev = None
    checked = 0
    for event in db.query(OpportunityEvent).filter(OpportunityEvent.mode == mode).order_by(OpportunityEvent.id).yield_per(500):
        if event.prev_hash != prev or event.hash != _event_hash(_body(event), prev):
            return {"ok": False, "checked": checked, "broken_at_id": event.id}
        prev = event.hash
        checked += 1
    return {"ok": True, "checked": checked, "broken_at_id": None}


def _event_dict(event: OpportunityEvent) -> dict:
    return {
        "id": event.id, "opportunity_id": event.opportunity_id, "setup": event.setup, "symbol": event.symbol,
        "mode": event.mode, "state": event.state, "from_state": event.from_state, "direction": event.direction,
        "approval": event.approval, "reason": event.reason, "payload": event.payload,
        "event_at": _utc(event.event_at).isoformat(), "hash": event.hash,
    }


def _levels_from(events: list[OpportunityEvent]) -> Levels | None:
    for event in reversed(events):
        p = event.payload or {}
        if event.state == SetupState.POSITION_OPEN.value and {"entry", "stop", "target"} <= p.keys():
            return Levels(float(p["entry"]), float(p["stop"]), float(p["target"]), int(p.get("max_hold_minutes", 0)))
        if event.state == SetupState.READY_TO_ENTER.value and "stop" in p and "reference_close" in p:
            entry = float(p["reference_close"])
            stop = float(p["stop"])
            side = 1 if event.direction == "long" else -1
            target = entry + side * float(p.get("target_r", 1.5)) * abs(entry - stop)
            return Levels(entry, stop, round(target, 5), int(p.get("max_hold_minutes", 0)))
    return None


def build_opportunity(events: list[OpportunityEvent], *, instrument_type: str = "BROKER_CFD") -> Opportunity:
    last = events[-1]
    evidence = tuple(
        EvidenceItem(evidence_id=f"ev:{e.hash[:12]}", kind="transition", text=e.reason, value=e.state,
                     source=f"ledger:{e.mode}", as_of=_utc(e.event_at).isoformat())
        for e in events
        if e.state not in (SetupState.INVALIDATED.value, SetupState.STOP.value)
    )
    counter = tuple(
        EvidenceItem(evidence_id=f"ev:{e.hash[:12]}", kind="transition", text=e.reason, value=e.state,
                     source=f"ledger:{e.mode}", as_of=_utc(e.event_at).isoformat())
        for e in events
        if e.state in (SetupState.INVALIDATED.value, SetupState.STOP.value, SetupState.EXPIRED.value)
    )
    return Opportunity(
        opportunity_id=last.opportunity_id, symbol=last.symbol, instrument_type=instrument_type, setup=last.setup,
        setup_version=last.setup_version, state=SetupState(last.state), direction=last.direction,
        approval=Approval(last.approval), data_as_of=_utc(last.event_at).isoformat(), levels=_levels_from(events),
        evidence=evidence, counter_evidence=counter,
    )


def current_opportunities(
    db: Session,
    *,
    mode: str | None = None,
    symbol: str | None = None,
    terminal_lookback: timedelta = timedelta(hours=24),
    now: datetime | None = None,
    limit_events: int = 2000,
) -> list[dict]:
    """Oportunidades vivas + as encerradas nas últimas `terminal_lookback`."""
    now = _utc(now or datetime.now(timezone.utc))
    query = db.query(OpportunityEvent)
    if mode:
        query = query.filter(OpportunityEvent.mode == mode)
    if symbol:
        query = query.filter(OpportunityEvent.symbol == symbol)
    rows = query.order_by(OpportunityEvent.id.desc()).limit(limit_events).all()
    grouped: dict[str, list[OpportunityEvent]] = {}
    for row in reversed(rows):
        grouped.setdefault(row.opportunity_id, []).append(row)
    out = []
    for events in grouped.values():
        state = SetupState(events[-1].state)
        if state in TERMINAL_STATES and now - _utc(events[-1].event_at) > terminal_lookback:
            continue
        out.append(build_opportunity(events).to_public_dict())
    out.sort(key=lambda o: (o["state"] in {s.value for s in TERMINAL_STATES}, -(o["progress"] or 0), o["data_as_of"]))
    return out


def timeline(db: Session, *, opportunity_id: str | None = None, symbol: str | None = None,
             since: datetime | None = None, limit: int = 200) -> list[dict]:
    query = db.query(OpportunityEvent)
    if opportunity_id:
        query = query.filter(OpportunityEvent.opportunity_id == opportunity_id)
    if symbol:
        query = query.filter(OpportunityEvent.symbol == symbol)
    if since:
        query = query.filter(OpportunityEvent.event_at >= _utc(since))
    rows = query.order_by(OpportunityEvent.id.desc()).limit(limit).all()
    return [_event_dict(row) for row in reversed(rows)]


def diff_since(db: Session, since: datetime, *, symbol: str | None = None, until: datetime | None = None) -> dict:
    """O que mudou entre `since` e `until`: oportunidades novas, avanços, encerramentos."""
    until = _utc(until or datetime.now(timezone.utc))
    since = _utc(since)
    query = db.query(OpportunityEvent).filter(OpportunityEvent.event_at > since, OpportunityEvent.event_at <= until)
    if symbol:
        query = query.filter(OpportunityEvent.symbol == symbol)
    events = query.order_by(OpportunityEvent.id).all()
    new, advanced, closed = [], [], []
    for event in events:
        item = {"opportunity_id": event.opportunity_id, "symbol": event.symbol, "setup": event.setup,
                "from": event.from_state, "to": event.state, "reason": event.reason,
                "at": _utc(event.event_at).isoformat(), "evidence_id": f"ev:{event.hash[:12]}"}
        if event.state == SetupState.BREAK_DETECTED.value:
            new.append(item)
        elif SetupState(event.state) in TERMINAL_STATES:
            closed.append(item)
        else:
            advanced.append(item)
    return {
        "since": since.isoformat(), "until": until.isoformat(), "event_count": len(events),
        "new_opportunities": new, "advanced": advanced, "closed": closed,
        "summary": f"{len(new)} nova(s), {len(advanced)} avanço(s) de estado, {len(closed)} encerrada(s).",
    }

