from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean

from sqlalchemy.orm import Session

from app.models import AlertLog, EarningsEvent, EconomicEvent, GlobalNewsItem, NewsItem, PriceSnapshot, WatchlistItem


def _latest_snapshot(db: Session, item: WatchlistItem) -> PriceSnapshot | None:
    return (
        db.query(PriceSnapshot)
        .filter(PriceSnapshot.watchlist_item_id == item.id)
        .order_by(PriceSnapshot.taken_at.desc())
        .first()
    )


def opportunity_score(db: Session, symbol: str) -> dict:
    symbol = symbol.upper().strip()
    item = db.query(WatchlistItem).filter(WatchlistItem.symbol == symbol).first()
    snap = _latest_snapshot(db, item) if item else None
    news = db.query(NewsItem).filter(NewsItem.symbol == symbol).order_by(NewsItem.published_at.desc()).limit(8).all()
    alerts = db.query(AlertLog).filter(AlertLog.symbol == symbol).order_by(AlertLog.triggered_at.desc()).limit(8).all()
    earnings = db.query(EarningsEvent).filter(EarningsEvent.symbol == symbol).order_by(EarningsEvent.event_date).first()

    score = 50
    factors = []
    if snap:
        if snap.change_pct >= 2:
            score += 12
            factors.append({"name": "Momentum", "impact": 12, "evidence": f"Alta recente de {snap.change_pct:.2f}%."})
        elif snap.change_pct <= -2:
            score -= 10
            factors.append({"name": "Pressao", "impact": -10, "evidence": f"Queda recente de {snap.change_pct:.2f}%."})
    if alerts:
        score += min(15, len(alerts) * 3)
        factors.append({"name": "Sinais", "impact": min(15, len(alerts) * 3), "evidence": f"{len(alerts)} alerta(s) recente(s)."})
    if news:
        score += min(10, len(news) * 2)
        factors.append({"name": "Fluxo de noticias", "impact": min(10, len(news) * 2), "evidence": f"{len(news)} noticia(s) recentes."})
    if earnings and earnings.event_date <= datetime.now(timezone.utc) + timedelta(days=7):
        score -= 12
        factors.append({"name": "Evento", "impact": -12, "evidence": "Earnings proximo aumenta risco de gap."})

    score = max(0, min(100, score))
    if score >= 70:
        label = "Setup forte com risco a validar"
    elif score >= 45:
        label = "Neutro, aguardar confirmacao"
    else:
        label = "Risco elevado ou sinal fraco"
    return {"symbol": symbol, "score": score, "label": label, "factors": factors}


def movement_explanation(db: Session, symbol: str) -> dict:
    symbol = symbol.upper().strip()
    item = db.query(WatchlistItem).filter(WatchlistItem.symbol == symbol).first()
    snap = _latest_snapshot(db, item) if item else None
    news = db.query(NewsItem).filter(NewsItem.symbol == symbol).order_by(NewsItem.published_at.desc()).limit(5).all()
    earnings = db.query(EarningsEvent).filter(EarningsEvent.symbol == symbol).order_by(EarningsEvent.event_date).first()
    macro = db.query(GlobalNewsItem).order_by(GlobalNewsItem.impact_score.desc(), GlobalNewsItem.published_at.desc()).limit(3).all()

    facts = []
    if snap:
        facts.append(f"{symbol} variou {snap.change_pct:+.2f}% no ultimo snapshot disponivel.")
        facts.append(f"Preco observado: {snap.price:.2f}.")
    related_events = [n.headline for n in news[:3]]
    if earnings:
        related_events.append(f"Earnings cadastrado para {earnings.event_date.date().isoformat()}.")
    related_events.extend(n.headline for n in macro[:2])
    hypotheses = []
    if snap and abs(snap.change_pct) >= 2 and news:
        hypotheses.append("O mercado pode estar reagindo ao fluxo recente de noticias, mas isso nao prova causalidade.")
    if earnings and earnings.event_date <= datetime.now(timezone.utc) + timedelta(days=7):
        hypotheses.append("Parte do movimento pode refletir ajuste de risco antes de earnings.")
    if not hypotheses:
        hypotheses.append("Nao ha evidencias suficientes para atribuir causa unica ao movimento.")
    return {"symbol": symbol, "facts": facts, "related_events": related_events, "hypotheses": hypotheses}


def market_radar(db: Session) -> dict:
    now = datetime.now(timezone.utc)
    items = db.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).all()
    scores = [opportunity_score(db, item.symbol) for item in items]
    earnings = (
        db.query(EarningsEvent)
        .filter(EarningsEvent.event_date >= now, EarningsEvent.event_date <= now + timedelta(days=10))
        .order_by(EarningsEvent.event_date)
        .limit(20)
        .all()
    )
    econ = (
        db.query(EconomicEvent)
        .filter(EconomicEvent.event_date >= now, EconomicEvent.event_date <= now + timedelta(days=10))
        .order_by(EconomicEvent.event_date)
        .limit(20)
        .all()
    )
    return {
        "scores": sorted(scores, key=lambda row: row["score"], reverse=True),
        "earnings": [{"symbol": e.symbol, "event_date": e.event_date.isoformat(), "eps_estimate": e.eps_estimate} for e in earnings],
        "economic_events": [{"event_name": e.event_name, "country": e.country, "event_date": e.event_date.isoformat(), "impact": e.impact} for e in econ],
    }


def weekly_brief(db: Session) -> dict:
    radar = market_radar(db)
    alerts = db.query(AlertLog).order_by(AlertLog.triggered_at.desc()).limit(20).all()
    avg_score = round(mean([s["score"] for s in radar["scores"]]), 1) if radar["scores"] else 0
    return {
        "title": "Resumo semanal de inteligencia",
        "summary": [
            f"{len(radar['scores'])} ativo(s) monitorado(s), score medio {avg_score}.",
            f"{len(alerts)} alerta(s) recentes entram no acompanhamento.",
            f"{len(radar['earnings'])} earnings e {len(radar['economic_events'])} evento(s) macro no radar.",
        ],
        "top_opportunities": radar["scores"][:5],
        "risks": [s for s in radar["scores"] if s["score"] < 45][:5],
        "next_events": radar["earnings"][:5] + radar["economic_events"][:5],
    }


def signal_quality(db: Session) -> list[dict]:
    rows = []
    symbols = [s for (s,) in db.query(AlertLog.symbol).distinct().all()]
    for symbol in symbols:
        alerts = db.query(AlertLog).filter(AlertLog.symbol == symbol).order_by(AlertLog.triggered_at.desc()).limit(50).all()
        delivered = sum(1 for a in alerts if a.delivered_telegram)
        rows.append(
            {
                "symbol": symbol,
                "alerts": len(alerts),
                "delivered": delivered,
                "noise_score": max(0, min(100, len(alerts) * 4 - delivered * 2)),
                "assessment": "Revisar regra" if len(alerts) > 20 else "Ok",
            }
        )
    return sorted(rows, key=lambda row: row["noise_score"], reverse=True)


DEFAULT_PLAYBOOKS = [
    {
        "name": "Earnings breakout",
        "description": "Monitora rompimento com volume perto de resultados.",
        "rule_preset": "PRICE_ABOVE + VOLUME_SPIKE; revisar calendario de earnings antes de agir.",
    },
    {
        "name": "Pullback em tendencia",
        "description": "Procura ativo forte corrigindo sem perder tendencia curta.",
        "rule_preset": "RSI_OVERSOLD leve + EMA curta acima da longa.",
    },
    {
        "name": "Queda pos-noticia",
        "description": "Separa queda tecnica de queda acompanhada por evento relevante.",
        "rule_preset": "PCT_CHANGE negativo + noticia recente + checagem macro.",
    },
]
