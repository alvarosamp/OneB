"""Small, read-only cross-asset context for assistant questions."""

import re
import unicodedata
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.market_data.macro_data import MACRO_INSTRUMENTS
from app.models import MacroIntelligenceSnapshot


ALIASES = {
    "GOLD": ("ouro", "gold", "xau", "xauusd", "xau/usd", "gc=f"),
    "WTI": ("wti", "cl=f"),
    "BRENT": ("brent", "bz=f"),
    "NASDAQ": ("nasdaq", "nq=f", "ustech", "us tech"),
    "SP500": ("s&p", "sp500", "s p 500", "es=f"),
    "DXY": ("dxy", "indice dolar", "dollar index", "dtwexbgs"),
    "US2Y": ("us2y", "us2yt=x", "2 anos", "2y"),
    "US5Y": ("us5y", "us5yt=x", "5 anos", "5y"),
    "US10Y": ("us10y", "us10yt=x", "10 anos", "10y"),
    "US30Y": ("us30y", "us30yt=x", "30 anos", "30y"),
    "EURUSD": ("eurusd", "eur/usd", "euro dolar"),
    "EURBRL": ("eurbrl", "eur/brl", "euro real"),
    "VIX": ("vix",),
}


def _normalize(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value.lower()) if not unicodedata.combining(c))


def _matches(value: str, alias: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", value) is not None


def _mentioned(value: str) -> list[str]:
    normalized = _normalize(value)
    found = [key for key, aliases in ALIASES.items() if any(_matches(normalized, alias) for alias in aliases)]
    if _matches(normalized, "petroleo") or _matches(normalized, "oil"):
        for key in ("WTI", "BRENT"):
            if key not in found:
                found.append(key)
    return found


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def build_cross_asset_context(
    db: Session, question: str, watchlist: list[dict], *, now: datetime | None = None
) -> dict:
    """Select evidence from the persisted macro scan; never fetch a new feed."""
    now = _utc(now or datetime.now(timezone.utc))
    watched = set()
    for item in watchlist:
        watched.update(_mentioned(f"{item.get('symbol', '')} {item.get('label', '')}"))
    explicit = _mentioned(question)
    targets = explicit[:2] or sorted(watched)[:2]
    if not targets:
        return {"status": "NO_MATCH", "reason": "Nenhum ativo macro identificado na pergunta ou watchlist."}

    snapshot = db.query(MacroIntelligenceSnapshot).order_by(MacroIntelligenceSnapshot.captured_at.desc()).first()
    if snapshot is None:
        return {"status": "UNAVAILABLE", "targets": targets, "reason": "Panorama macro historico ainda nao calculado."}
    captured_at = _utc(snapshot.captured_at)
    if captured_at > now + timedelta(minutes=10) or now - captured_at > timedelta(days=4):
        return {"status": "STALE", "targets": targets, "as_of": captured_at.isoformat(), "reason": "Panorama macro antigo; nao usar como leitura atual."}

    payload = snapshot.payload or {}
    quality = {row.get("key"): row for row in (payload.get("data_quality") or {}).get("instruments", [])}
    windows = payload.get("correlation_windows") or {}
    matrices = {
        window: {row.get("key"): row.get("values") or {} for row in (windows.get(window) or {}).get("matrix", [])}
        for window in ("20", "60", "3m", "6m")
    }
    dynamics = {
        frozenset((row.get("left"), row.get("right"))): row.get("status")
        for row in payload.get("relationship_dynamics") or []
    }

    def fresh(key: str) -> bool:
        row = quality.get(key) or {}
        if row.get("status") != "FRESH" or not row.get("as_of"):
            return False
        try:
            as_of = _utc(datetime.fromisoformat(row["as_of"].replace("Z", "+00:00")))
        except ValueError:
            return False
        return as_of <= now + timedelta(minutes=10) and now - as_of <= timedelta(days=4)

    def instrument(key: str) -> dict:
        source, symbol, name = MACRO_INSTRUMENTS[key]
        trend = (payload.get("trends") or {}).get(key) or {}
        move = (payload.get("daily_moves") or {}).get(key) or {}
        return {
            "key": key, "name": name, "source": source, "source_symbol": symbol,
            "outside_watchlist": key not in watched,
            "data_as_of": (quality.get(key) or {}).get("as_of"),
            "trend": {field: trend.get(field) for field in ("direction", "strength", "change_20d", "change_60d", "change_unit")},
            "latest_daily_move": {field: move.get(field) for field in ("move", "unit", "as_of")},
        }

    selected = []
    for target in targets:
        if not fresh(target):
            selected.append({"key": target, "status": "NO_FRESH_HISTORY", "data_as_of": (quality.get(target) or {}).get("as_of")})
            continue
        peers = []
        for other, corr60 in (matrices["60"].get(target) or {}).items():
            if other == target or other not in MACRO_INSTRUMENTS or not fresh(other) or not isinstance(corr60, (int, float)) or abs(corr60) < 0.25:
                continue
            peers.append((other, corr60))
        peers.sort(key=lambda pair: (pair[0] in watched, -abs(pair[1])))
        relationships = []
        for other, corr60 in peers[:5]:
            relationships.append({
                "asset": instrument(other),
                "correlation_20_sessions": matrices["20"].get(target, {}).get(other),
                "correlation_60_sessions": corr60,
                "correlation_3_months": matrices["3m"].get(target, {}).get(other),
                "correlation_6_months": matrices["6m"].get(target, {}).get(other),
                "relationship_change": dynamics.get(frozenset((target, other))),
            })
        selected.append({"asset": instrument(target), "status": "AVAILABLE", "related_assets": relationships})

    overview = [instrument(key) for key in sorted(watched) if key in MACRO_INSTRUMENTS and fresh(key)] if not explicit else []
    return {
        "status": "AVAILABLE", "as_of": captured_at.isoformat(), "targets": selected,
        "watchlist_overview": overview,
        "methodology": "Correlacoes de variacoes diarias na mesma sessao; juros usam diferencas de yield e os demais retornos percentuais. Selecao por magnitude em 60 sessoes, minimo 0,25; nao indica causalidade ou previsao.",
        "source_caveat": "DXY neste banco e DTWEXBGS (indice amplo do Fed), nao o contrato ICE DXY. Ouro e petroleo usam futuros, que podem diferir do spot/CFD da watchlist.",
    }
