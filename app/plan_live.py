"""Placar ao vivo do plano de trade (pré-registro configs/preregistration/plan_live_v1.json).

Todo dia útil, às 10:30 de Brasília, registra por regra fixa um plano de compra e um de venda
(stop 1,5 ATR do H1, alvos 1R/2R/3R) e confere nas barras seguintes se cada alvo veio antes do stop.
Tudo é reconstruído das barras de 5 min: ninguém escolhe dia, direção ou resultado.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd

ENTRY_UTC = (13, 30)  # 10:30 de Brasília (UTC-3, sem horário de verão)
STOP_ATR = 1.5
TARGETS = (1.0, 2.0, 3.0)
HORIZON = pd.Timedelta(hours=24)
LIVE_START = date(2026, 10, 15)
RETRO_START = date(2026, 8, 5)
MIN_FOR_VERDICT = 60


def _utc(m5: pd.DataFrame) -> pd.DataFrame:
    d = m5[["open", "high", "low", "close"]].dropna().copy()
    idx = pd.DatetimeIndex(d.index)
    d.index = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    return d[~d.index.duplicated()].sort_index()


def h1_atr(m5: pd.DataFrame) -> pd.Series:
    """ATR(14) do H1, indexado pelo instante em que a hora fecha (só horas completas)."""
    h = m5.resample("1h").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    prev = h["close"].shift()
    tr = pd.concat([h["high"] - h["low"], (h["high"] - prev).abs(), (h["low"] - prev).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    atr.index = atr.index + pd.Timedelta(hours=1)
    return atr.dropna()


def _resolve(bars: pd.DataFrame, entry: float, stop_dist: float, side: int, target_r: float, complete: bool) -> str:
    stop_px, tp_px = entry - side * stop_dist, entry + side * target_r * stop_dist
    hi, lo = bars["high"].to_numpy(), bars["low"].to_numpy()
    for h, l in zip(hi, lo):
        hit_stop = l <= stop_px if side == 1 else h >= stop_px
        hit_tp = h >= tp_px if side == 1 else l <= tp_px
        if hit_stop:
            return "stop"  # inclusive quando os dois tocam na mesma barra
        if hit_tp:
            return "hit"
    return "expired" if complete else "open"


def build_plans(m5: pd.DataFrame, spread: float, start: date, end: date | None = None) -> list[dict]:
    d = _utc(m5)
    if d.empty:
        return []
    atr = h1_atr(d)
    last_time = d.index[-1]
    rows = []
    for day in sorted({t.date() for t in d.index}):
        if day < start or (end is not None and day >= end) or day.weekday() >= 5:
            continue
        ts = pd.Timestamp(datetime(day.year, day.month, day.day, *ENTRY_UTC, tzinfo=timezone.utc))
        if ts not in d.index:
            continue
        known = atr[atr.index <= ts]
        if known.empty or not np.isfinite(known.iloc[-1]) or known.iloc[-1] <= 0:
            continue
        a = float(known.iloc[-1])
        stop_dist = STOP_ATR * a
        window = d[(d.index >= ts) & (d.index < ts + HORIZON)]
        complete = last_time >= ts + HORIZON - pd.Timedelta(minutes=5)
        open_px = float(d.loc[ts, "open"])
        for direction, side in (("long", 1), ("short", -1)):
            entry = open_px + side * spread
            rows.append({"date": day.isoformat(), "direction": direction, "entry": entry, "stop_distance": stop_dist,
                         "results": {str(int(t)): _resolve(window, entry, stop_dist, side, t, complete) for t in TARGETS}})
    return rows


def wilson(hits: int, n: int, z: float = 1.96) -> tuple[float, float] | tuple[None, None]:
    if n == 0:
        return None, None
    p = hits / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, mid - half), min(1.0, mid + half)


def summarize(rows: list[dict], announced: dict[tuple[str, float], float | None]) -> dict:
    out = {}
    for direction in ("long", "short"):
        mine = [r for r in rows if r["direction"] == direction]
        targets = []
        for t in TARGETS:
            res = [r["results"][str(int(t))] for r in mine]
            closed = [x for x in res if x != "open"]
            hits = sum(x == "hit" for x in closed)
            lo, hi = wilson(hits, len(closed))
            ann = announced.get((direction, t))
            targets.append({"target_r": t, "closed": len(closed), "hits": hits, "open": len(res) - len(closed),
                            "rate": hits / len(closed) if closed else None, "wilson95": [lo, hi] if lo is not None else None,
                            "announced": ann, "consistent": (lo <= ann <= hi) if (lo is not None and ann is not None) else None})
        n = min((x["closed"] for x in targets), default=0)
        status = "acumulando" if n < MIN_FOR_VERDICT else ("confirmado" if all(x["consistent"] for x in targets) else "divergente")
        out[direction] = {"plans": len(mine), "status": status, "targets": targets}
    return out


def _is_closed(results: dict) -> bool:
    return all(v != "open" for v in results.values())


def resolve_stored(m5: pd.DataFrame, plan_date: str, direction: str, entry: float, stop_dist: float,
                   normalized: bool = False) -> dict[str, str] | None:
    """Confere um plano JÁ GRAVADO com a entrada e o stop gravados (nunca com os da reconstrução)."""
    d = m5 if normalized else _utc(m5)
    if d.empty:
        return None
    day = date.fromisoformat(plan_date)
    ts = pd.Timestamp(datetime(day.year, day.month, day.day, *ENTRY_UTC, tzinfo=timezone.utc))
    window = d[(d.index >= ts) & (d.index < ts + HORIZON)]
    if window.empty:
        return None
    complete = d.index[-1] >= ts + HORIZON - pd.Timedelta(minutes=5)
    side = 1 if direction == "long" else -1
    return {str(int(t)): _resolve(window, entry, stop_dist, side, t, complete) for t in TARGETS}


def record(db, asset: str, rows: list[dict], rule_sha256: str, m5: pd.DataFrame | None = None) -> dict:
    """Grava os planos novos e avança os em andamento. Plano encerrado no banco nunca é reescrito.

    Em andamento, o resultado é conferido com a entrada e o stop GRAVADOS (resolve_stored), não com os da
    reconstrução: se a fonte corrigir barras antigas, o ATR muda um pouco, mas o plano registrado não."""
    from sqlalchemy.exc import IntegrityError

    from app.models import PlanLiveRecord, utcnow

    existing = {(r.plan_date, r.direction): r for r in db.query(PlanLiveRecord).filter(PlanLiveRecord.asset == asset).all()}
    inserted = updated = 0
    for row in rows:
        closed = _is_closed(row["results"])
        if (row["date"], row["direction"]) not in existing:
            try:
                with db.begin_nested():  # outro processo pode ter gravado o mesmo plano agora: ignora e segue
                    db.add(PlanLiveRecord(asset=asset, plan_date=row["date"], direction=row["direction"], entry=row["entry"],
                                          stop_distance=row["stop_distance"], results=dict(row["results"]), closed=closed,
                                          rule_sha256=rule_sha256, closed_at=utcnow() if closed else None))
                inserted += 1
            except IntegrityError:
                pass
    d = _utc(m5) if m5 is not None else None
    for rec in existing.values():
        if rec.closed:
            continue
        fresh = resolve_stored(d, rec.plan_date, rec.direction, rec.entry, rec.stop_distance, normalized=True) if d is not None else None
        if fresh is None:
            continue
        # alvo já decidido não volta atrás; só os em andamento avançam
        merged = {k: (rec.results.get(k) if rec.results.get(k) not in (None, "open") else v) for k, v in fresh.items()}
        if merged != rec.results:
            rec.results = merged
            rec.closed = _is_closed(merged)
            rec.closed_at = utcnow() if rec.closed else None
            updated += 1
    db.commit()
    return {"inserted": inserted, "updated": updated}


def stored(db, asset: str, start: date) -> list[dict]:
    from app.models import PlanLiveRecord

    q = (db.query(PlanLiveRecord).filter(PlanLiveRecord.asset == asset, PlanLiveRecord.plan_date >= start.isoformat())
         .order_by(PlanLiveRecord.plan_date, PlanLiveRecord.direction))
    out = []
    for r in q.all():
        day = date.fromisoformat(r.plan_date)
        entry_ts = datetime(day.year, day.month, day.day, *ENTRY_UTC, tzinfo=timezone.utc)
        rec = r.recorded_at if r.recorded_at.tzinfo else r.recorded_at.replace(tzinfo=timezone.utc)
        out.append({"date": r.plan_date, "direction": r.direction, "entry": r.entry, "stop_distance": r.stop_distance,
                    "results": dict(r.results), "stored": True,
                    # gravado enquanto o plano ainda estava aberto (até 24 h da entrada) = ao vivo; depois disso, reconstrução tardia
                    "recorded_live": bool(rec <= entry_ts + HORIZON.to_pytimedelta())})
    return out


def refresh_open(saved: list[dict], m5: pd.DataFrame | None) -> list[dict]:
    """Para a leitura: confere em memória os planos gravados ainda abertos (sem gravar nada)."""
    if m5 is None or m5.empty:
        return saved
    d = _utc(m5)
    out = []
    for r in saved:
        if any(v == "open" for v in r["results"].values()):
            fresh = resolve_stored(d, r["date"], r["direction"], r["entry"], r["stop_distance"], normalized=True)
            if fresh:
                r = {**r, "results": {k: (v if v != "open" else fresh.get(k, v)) for k, v in r["results"].items()}}
        out.append(r)
    return out


def merge(saved: list[dict], rebuilt: list[dict]) -> list[dict]:
    """Banco primeiro (é o histórico que fica); a reconstrução só completa o que ainda não foi gravado."""
    out = {(r["date"], r["direction"]): r for r in rebuilt}
    out.update({(r["date"], r["direction"]): r for r in saved})
    return [out[k] for k in sorted(out)]
