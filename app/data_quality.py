from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.market_data import finnhub_client, yfinance_client  # noqa: F401 legacy monkeypatch compatibility
from app.market_data import service as market_data_service
from app.models import PriceSnapshot, WatchlistItem

STALE_LIMIT_MINUTES = {
    "finnhub": 90,
    "local_snapshot": 24 * 60,
    "tiingo": 3 * 24 * 60,
    "yfinance": 3 * 24 * 60,
}


@dataclass
class ProviderCheck:
    provider: str
    available: bool
    price: float | None = None
    change_pct: float | None = None
    timestamp: datetime | None = None
    error: str = ""


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


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def check_finnhub(symbol: str) -> ProviderCheck:
    try:
        quote = finnhub_client.get_quote(symbol)
    except Exception as exc:
        return ProviderCheck("finnhub", False, error=str(exc))
    if quote is None:
        return ProviderCheck("finnhub", False, error="Sem cotacao")
    return ProviderCheck("finnhub", True, quote.price, quote.change_pct, datetime.now(timezone.utc))


def check_market_data(symbol: str) -> ProviderCheck:
    quote = market_data_service.get_quote(symbol, refresh=False)
    if quote is None:
        return ProviderCheck("market_data", False, error="Sem historico")
    return ProviderCheck(quote.provider, True, quote.price, quote.change_pct, quote.provider_time)


def validate_symbol_data(db: Session, symbol: str) -> dict:
    symbol = symbol.upper().strip()
    checks = [check_finnhub(symbol), check_market_data(symbol)]
    latest_local = _latest_snapshot(db, symbol)
    if latest_local:
        checks.append(
            ProviderCheck(
                "local_snapshot",
                True,
                latest_local.price,
                latest_local.change_pct,
                _aware_utc(latest_local.taken_at),
            )
        )

    now = datetime.now(timezone.utc)
    stale_providers: list[str] = []
    available = []
    for check in checks:
        if not check.available or check.price is None:
            continue
        timestamp = _aware_utc(check.timestamp)
        limit = STALE_LIMIT_MINUTES.get(check.provider, 24 * 60)
        age = ((now - timestamp).total_seconds() / 60) if timestamp else None
        if age is not None and age > limit:
            stale_providers.append(check.provider)
            continue
        available.append(check)
    prices = [check.price for check in available if check.price is not None]
    reference = prices[0] if prices else None
    max_divergence_pct = 0.0
    if reference:
        max_divergence_pct = max(abs((price - reference) / reference * 100) for price in prices)

    freshest = None
    if available:
        timestamps = [_aware_utc(check.timestamp) for check in available if check.timestamp is not None]
        timestamps = [ts for ts in timestamps if ts is not None]
        freshest = max(timestamps) if timestamps else None
    age_minutes = ((now - freshest).total_seconds() / 60) if freshest else None

    issues = []
    if len(available) < 2:
        issues.append("Menos de duas fontes disponiveis para comparacao.")
    if max_divergence_pct > 1:
        issues.append(f"Divergencia alta entre fontes: {max_divergence_pct:.2f}%.")
    if age_minutes is not None and age_minutes > 3 * 24 * 60:
        issues.append(f"Dado comparavel mais recente tem {age_minutes:.0f} minutos.")
    if stale_providers and not available:
        issues.append(f"Fontes stale ignoradas: {', '.join(sorted(stale_providers))}.")

    if not available:
        confidence = "LOW"
    elif issues:
        confidence = "MEDIUM"
    else:
        confidence = "HIGH"

    return {
        "symbol": symbol,
        "confidence": confidence,
        "max_divergence_pct": round(max_divergence_pct, 4),
        "freshest_age_minutes": round(age_minutes, 1) if age_minutes is not None else None,
        "issues": issues,
        "stale_providers_ignored": sorted(stale_providers),
        "providers": [
            {
                "provider": check.provider,
                "available": check.available,
                "price": round(check.price, 4) if check.price is not None else None,
                "change_pct": round(check.change_pct, 4) if check.change_pct is not None else None,
                "timestamp": check.timestamp.isoformat() if check.timestamp else None,
                "error": check.error,
            }
            for check in checks
        ],
    }


def validate_watchlist_data(db: Session) -> dict:
    items = db.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).all()
    rows = [validate_symbol_data(db, item.symbol) for item in items]
    confidence_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for row in rows:
        confidence_counts[row["confidence"]] += 1
    return {"rows": rows, "confidence_counts": confidence_counts}


def quality_gate(db: Session, symbol: str, min_confidence: str = "MEDIUM") -> dict:
    levels = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    result = validate_symbol_data(db, symbol)
    allowed = levels[result["confidence"]] >= levels[min_confidence]
    return {
        "allowed": allowed,
        "required_confidence": min_confidence,
        "reason": "" if allowed else _quality_reason(result),
        **result,
    }


def _quality_reason(result: dict) -> str:
    issues = result.get("issues") or []
    text = " ".join(issues).lower()
    if "divergencia" in text:
        return "DATA_CONFLICT"
    if "minutos" in text:
        return "STALE_DATA"
    if "menos de duas fontes" in text or not result.get("providers"):
        return "PROVIDER_UNAVAILABLE"
    return "DATA_QUALITY_LOW"
