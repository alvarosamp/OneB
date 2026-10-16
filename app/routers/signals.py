"""'Avaliar um sinal': o cliente cola o sinal que recebeu; o OneB mede a chance real de cada alvo e acompanha a fonte.

Rotas:
- POST /api/signals/evaluate  -> avaliação (e grava no placar se track=true)
- GET  /api/signals           -> sinais acompanhados do usuário e o placar por fonte
- DELETE /api/signals/{id}    -> remove um sinal do placar (só o dono)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import signal_eval as se
from app.auth import get_current_user
from app.db import get_db
from app.models import SignalRecord, utcnow
from app.routers import asset_brief as ab

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/signals", tags=["signals"], dependencies=[Depends(get_current_user)])

HIGH_COST = 0.10
SHORT_STOP_ATR = 0.5


class EvaluateRequest(BaseModel):
    text: str = Field(min_length=5, max_length=2000)
    source: str = Field(default="", max_length=64)
    balance: float | None = Field(default=None, gt=0)
    risk_pct: float | None = Field(default=None, gt=0, le=10)
    track: bool = True


def _hour_quality(key: str, now: datetime) -> dict | None:
    guide = ab._result("hours_guide.json") or {}
    hours = ((guide.get("assets") or {}).get(key) or {}).get("hours") or []
    ny_hour = now.astimezone(ab.NEW_YORK).hour
    return next(({"class": h["class"], "reason": h["reason"]} for h in hours if h["ny_hour"] == ny_hour), None)


def evaluate(text: str, db: Session, now: datetime, balance: float | None = None, risk_pct: float | None = None,
             m5: pd.DataFrame | None = None) -> dict:
    first = se.parse_signal(text)
    if "error" in first and "asset" not in first:
        return {"ok": False, "error": first["error"]}
    key = first["asset"]
    market = ab.response_cache.cached(f"brief:market:{key}", 120, lambda: ab._market(key)) if m5 is None else {}
    m5 = m5 if m5 is not None else ab._m5(key)
    ref = market.get("price") or (float(m5["close"].iloc[-1]) if m5 is not None and not m5.empty else None)
    sig = se.parse_signal(text, {key: ref} if ref else None)
    if "error" in sig:
        return {"ok": False, "error": sig["error"], "asset": key}
    if m5 is None or m5.empty:
        return {"ok": False, "error": "Sem barras de 5 minutos agora para medir a chance dos alvos.", "asset": key, "signal": sig}
    broker = ab.BROKER[key]
    spread = broker.get("spread_points") or 0.0
    atr = se.current_atr(m5)
    if not atr:
        return {"ok": False, "error": "Sem ATR de 1 hora agora.", "asset": key, "signal": sig}
    stop_atr = sig["stop_distance"] / atr
    # taxa-base NEUTRA: média de compra e venda nas mesmas entradas, para a tendência dos últimos 60 dias não
    # parecer mérito do sinal (num período de queda, qualquer venda "acerta" mais)
    rates_long = se.base_rates(m5, "long", stop_atr, sig["target_r"], spread)
    rates_short = se.base_rates(m5, "short", stop_atr, sig["target_r"], spread)
    rates = {**rates_long, "targets": [se.neutral(a, b) for a, b in zip(rates_long["targets"], rates_short["targets"])]}
    targets = []
    for price, dist, r, rate in zip(sig["targets"], sig["target_distances"], sig["target_r"], rates["targets"]):
        targets.append({"price": price, "distance": dist, "target_r": r, **{k: rate[k] for k in ("p_target", "ci95", "p_stop", "p_open_24h", "mean_r", "breakeven_p", "n")}})
    warnings = []
    share = spread / sig["stop_distance"] if sig["stop_distance"] else None
    if share is not None and share >= HIGH_COST:
        warnings.append(f"O spread do {broker['symbol']} ({ab._br(spread, 2 if spread >= 0.1 else 5)}) come {ab._br(share * 100, 0)}% desse stop: custo alto.")
    if stop_atr < SHORT_STOP_ATR:
        warnings.append(f"Stop curto: {ab._br(stop_atr, 2)} vez o movimento típico de 1 hora. O ruído normal costuma alcançá-lo.")
    for e in ab._events(key, db, now):
        if e.get("measured") and ab._as_utc(e["event_date"]) <= pd.Timestamp(now) + pd.Timedelta(hours=24):
            warnings.append(f"{e['event_name']} nas próximas 24 h: o movimento costuma multiplicar por {ab._br(e['post30'], 1)} na primeira meia hora.")
    hour = _hour_quality(key, now)
    if hour and hour["class"] in ("evitar", "parado", "fechado"):
        warnings.append(f"Horário: {hour['reason']}")
    contract, vmin, vstep = broker["contract_size"], broker["volume_min"], broker["volume_step"]
    sizing = None
    if balance and risk_pct:
        from app.oneb_ai.tools import position_size

        sizing = position_size(balance, risk_pct, sig["stop_distance"], contract, vmin, vstep, spread)
    min_lot_risk = sig["stop_distance"] * contract * vmin
    tp1 = targets[0]
    verdict = (f"Com esse stop e esse primeiro alvo, entradas de hora em hora nos últimos 60 dias bateram o TP1 em "
               f"{ab._br(tp1['p_target'] * 100, 0)}% das vezes; para empatar seria preciso {ab._br(tp1['breakeven_p'] * 100, 0)}%. "
               f"Resultado médio de quem sai no TP1: {ab._sgn(tp1['mean_r'], 2)}R por trade. "
               "Isso é a taxa-base de QUALQUER entrada com esses tamanhos: o sinal só prova valor se o placar dele superar isso.")
    return {"ok": True, "asset": key, "label": ab.ASSETS[key]["label"], "symbol": broker["symbol"], "signal": sig,
            "stop_atr": stop_atr, "atr_h1": atr, "targets": targets, "sample": {k: rates[k] for k in ("n", "from", "to")},
            "spread": spread, "spread_share": share, "warnings": warnings, "sizing": sizing,
            "min_lot": {"volume_min": vmin, "risk_usd": min_lot_risk, "balance_1pct": min_lot_risk / 0.01},
            "verdict": verdict,
            "method": "Taxa-base medida nas barras de 5 min do gráfico (últimos ~60 dias), entradas de hora em hora, média de compra e venda "
                      "(tira a tendência do período), stop proporcional ao ATR "
                      "de 1 hora como o do sinal, spread da corretora, até 24 h; stop e alvo na mesma barra contam como stop. "
                      "As distâncias valem a partir do seu preço no MT5."}


@router.post("/evaluate")
def evaluate_endpoint(payload: EvaluateRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    result = evaluate(payload.text, db, now, payload.balance, payload.risk_pct)
    if result["ok"] and payload.track:
        sig = result["signal"]
        rec = SignalRecord(user_id=getattr(user, "id", None), source=(payload.source or "Sem nome").strip()[:64], asset=result["asset"],
                           direction=sig["direction"], entry=sig["entry"], stop=sig["stop"], targets=sig["targets"],
                           stop_distance=sig["stop_distance"], target_distances=sig["target_distances"],
                           base_p=[t["p_target"] for t in result["targets"]], base_mean_r=[t["mean_r"] for t in result["targets"]],
                           raw_text=payload.text, results=["open"] * len(sig["targets"]), result_r=[None] * len(sig["targets"]),
                           created_at=now)
        db.add(rec)
        db.commit()
        result["tracked_id"] = rec.id
    return result


def _refresh(rec: SignalRecord, m5: pd.DataFrame | None) -> dict:
    """Resultado atual de um sinal: o gravado; os alvos ainda abertos são conferidos em memória (sem gravar)."""
    results, rr = list(rec.results), list(rec.result_r)
    if not rec.closed and m5 is not None and not m5.empty:
        fresh = se.resolve_signal(m5, rec.created_at, rec.direction, rec.stop_distance, rec.target_distances,
                                  ab.BROKER[rec.asset].get("spread_points") or 0.0)
        if fresh:
            for i, (old, new) in enumerate(zip(results, fresh["results"])):
                if old == "open":
                    results[i], rr[i] = new, fresh["result_r"][i]
    return {"results": results, "result_r": rr}


def scoreboard(rows: list[dict]) -> list[dict]:
    """Placar por fonte: no TP1 (e em cada alvo), a taxa observada contra a taxa-base medida na hora de cada sinal."""
    out = []
    for source in sorted({r["source"] for r in rows}):
        mine = [r for r in rows if r["source"] == source]
        n_targets = max(len(r["results"]) for r in mine)
        per_tp = []
        for i in range(n_targets):
            done = [r for r in mine if len(r["results"]) > i and r["results"][i] != "open"]
            hits = sum(r["results"][i] == "hit" for r in done)
            expected = sum(r["base_p"][i] for r in done if r["base_p"][i] is not None)
            rs = [r["result_r"][i] for r in done if r["result_r"][i] is not None]
            per_tp.append({"target": i + 1, "closed": len(done), "hits": hits, "rate": hits / len(done) if done else None,
                           "ci95": se.wilson(hits, len(done)), "expected_rate": expected / len(done) if done else None,
                           "mean_r": sum(rs) / len(rs) if rs else None})
        out.append({"source": source, "signals": len(mine), "open": sum(any(x == "open" for x in r["results"]) for r in mine), "targets": per_tp})
    return out


@router.get("")
def list_signals(db: Session = Depends(get_db), user=Depends(get_current_user)):
    recs = (db.query(SignalRecord).filter(SignalRecord.user_id == getattr(user, "id", None))
            .order_by(SignalRecord.created_at.desc()).limit(200).all())
    bars = {key: ab._m5(key) for key in {r.asset for r in recs if not r.closed}}
    rows = []
    for r in recs:
        cur = _refresh(r, bars.get(r.asset))
        rows.append({"id": r.id, "source": r.source, "asset": r.asset, "label": ab.ASSETS[r.asset]["label"] if r.asset in ab.ASSETS else r.asset,
                     "direction": r.direction, "entry": r.entry, "stop": r.stop, "targets": r.targets,
                     "target_r": [d / r.stop_distance for d in r.target_distances], "base_p": r.base_p,
                     "created_at": (r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=timezone.utc)).isoformat(), **cur})
    return {"signals": rows, "scoreboard": scoreboard(rows),
            "note": "Cada sinal é conferido como entrada a mercado no momento em que foi colado, pelas distâncias do sinal, até 24 h. "
                    "Com poucos sinais, o placar ainda é ruído."}


@router.delete("/{signal_id}")
def delete_signal(signal_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rec = db.query(SignalRecord).filter(SignalRecord.id == signal_id, SignalRecord.user_id == getattr(user, "id", None)).first()
    if rec is None:
        raise HTTPException(404, "Sinal não encontrado.")
    db.delete(rec)
    db.commit()
    return {"deleted": signal_id}


def resolve_open(db: Session) -> int:
    """Job do agendador: grava o resultado dos sinais abertos (alvo decidido não muda). Retorna quantos mudaram."""
    recs = db.query(SignalRecord).filter(SignalRecord.closed.is_(False)).all()
    bars = {key: ab._m5(key) for key in {r.asset for r in recs}}
    changed = 0
    for r in recs:
        cur = _refresh(r, bars.get(r.asset))
        if cur["results"] != list(r.results):
            r.results, r.result_r = cur["results"], cur["result_r"]
            if all(x != "open" for x in r.results):
                r.closed, r.closed_at = True, utcnow()
            changed += 1
    db.commit()
    return changed
