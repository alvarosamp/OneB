from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import PriceSnapshot, Transaction, TransactionSide, WatchlistItem

MAX_POSITION_PCT = float(os.getenv("RISK_MAX_POSITION_PCT", "20"))
MAX_SINGLE_SYMBOL_EXPOSURE_PCT = float(os.getenv("RISK_MAX_SINGLE_SYMBOL_EXPOSURE_PCT", "35"))
MAX_DATA_AGE_MINUTES = float(os.getenv("RISK_MAX_DATA_AGE_MINUTES", "1440"))


@dataclass(frozen=True)
class RiskCheck:
    allowed: bool
    level: str
    reasons: list[str] = field(default_factory=list)
    kill_switches: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _latest_snapshot(db: Session, symbol: str) -> PriceSnapshot | None:
    item = db.query(WatchlistItem).filter(WatchlistItem.symbol == symbol.upper()).first()
    if item is None:
        return None
    return (
        db.query(PriceSnapshot)
        .filter(PriceSnapshot.watchlist_item_id == item.id)
        .order_by(PriceSnapshot.taken_at.desc())
        .first()
    )


def _symbol_market_value(db: Session, user_id: int | None, symbol: str, fallback_price: float) -> float:
    if user_id is None:
        return 0.0
    txs = db.query(Transaction).filter(Transaction.user_id == user_id, Transaction.symbol == symbol.upper()).all()
    quantity = 0.0
    for tx in txs:
        quantity += tx.quantity if tx.side == TransactionSide.BUY else -tx.quantity
    return max(0.0, quantity * fallback_price)


def evaluate_decision(
    db: Session,
    *,
    user_id: int | None,
    symbol: str,
    action: str,
    suggested_size_pct: float,
    price: float,
    quality_gate: dict | None = None,
    portfolio_value: float = 10000.0,
) -> RiskCheck:
    reasons: list[str] = []
    kill_switches: list[str] = []
    metrics: dict = {"suggested_size_pct": suggested_size_pct, "portfolio_value": portfolio_value}

    if quality_gate and not quality_gate.get("allowed", True):
        kill_switches.append(quality_gate.get("reason") or "DATA_QUALITY_LOW")
        reasons.append("Quality gate bloqueou a decisão antes do risco de carteira.")

    if suggested_size_pct > MAX_POSITION_PCT:
        kill_switches.append("MAX_POSITION")
        reasons.append(f"Tamanho sugerido {suggested_size_pct:.1f}% excede limite {MAX_POSITION_PCT:.1f}%.")

    snapshot = _latest_snapshot(db, symbol)
    if snapshot is not None:
        taken_at = snapshot.taken_at
        if taken_at.tzinfo is None:
            taken_at = taken_at.replace(tzinfo=timezone.utc)
        age_minutes = (datetime.now(timezone.utc) - taken_at.astimezone(timezone.utc)).total_seconds() / 60
        metrics["data_age_minutes"] = round(age_minutes, 1)
        if age_minutes > MAX_DATA_AGE_MINUTES:
            kill_switches.append("MAX_DATA_AGE")
            reasons.append(f"Dado local tem {age_minutes:.0f} minutos.")

    exposure = _symbol_market_value(db, user_id, symbol, price)
    proposed = portfolio_value * max(suggested_size_pct, 0) / 100
    exposure_pct = ((exposure + proposed) / portfolio_value * 100) if portfolio_value else 0.0
    metrics["single_symbol_exposure_pct"] = round(exposure_pct, 2)
    if exposure_pct > MAX_SINGLE_SYMBOL_EXPOSURE_PCT:
        kill_switches.append("MAX_SINGLE_SYMBOL_EXPOSURE")
        reasons.append(
            f"Exposição projetada em {symbol.upper()} iria para {exposure_pct:.1f}% "
            f"(limite {MAX_SINGLE_SYMBOL_EXPOSURE_PCT:.1f}%)."
        )

    if action in {"WAIT", "AVOID", "NO_TRADE"}:
        metrics["risk_note"] = "Sem aumento de exposição solicitado."

    allowed = not kill_switches
    level = "BLOCKED" if not allowed else "MEDIUM" if suggested_size_pct >= 10 else "LOW"
    if allowed and not reasons:
        reasons.append("Risco dentro dos limites configurados para a decisão.")
    return RiskCheck(allowed=allowed, level=level, reasons=reasons, kill_switches=kill_switches, metrics=metrics)
