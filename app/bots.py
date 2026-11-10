from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.intelligence import market_radar, movement_explanation, opportunity_score, signal_quality, weekly_brief
from app.market_data import service as market_data_service
from app.models import PriceSnapshot, WatchlistItem


@dataclass
class BotMessage:
    title: str
    body: str


def refresh_symbol_with_real_market_data(db: Session, symbol: str) -> PriceSnapshot | None:
    symbol = symbol.upper().strip()
    history = market_data_service.get_bars(symbol, period="5d", interval="1d")
    if history.empty:
        return None

    close = history["close"].dropna()
    volume = history["volume"].dropna()
    if close.empty:
        return None

    latest = float(close.iloc[-1])
    previous = float(close.iloc[-2]) if len(close) >= 2 else latest
    change_pct = ((latest - previous) / previous * 100) if previous else 0.0
    latest_volume = float(volume.iloc[-1]) if not volume.empty else 0.0

    item = db.query(WatchlistItem).filter(WatchlistItem.symbol == symbol).first()
    if item is None:
        item = WatchlistItem(symbol=symbol, label=symbol)
        db.add(item)
        db.commit()
        db.refresh(item)

    snapshot = PriceSnapshot(
        watchlist_item_id=item.id,
        price=latest,
        change_pct=change_pct,
        volume=latest_volume,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def radar_bot(db: Session) -> BotMessage:
    radar = market_radar(db)
    scores = radar["scores"][:5]
    if not scores:
        return BotMessage("Radar", "Watchlist vazia. Adicione ativos para receber um radar.")

    lines = ["Radar de mercado:"]
    for row in scores:
        lines.append(f"- {row['symbol']}: {row['score']}/100 - {row['label']}")
    lines.append(f"Eventos no radar: {len(radar['earnings'])} earnings, {len(radar['economic_events'])} macro.")
    return BotMessage("Radar", "\n".join(lines))


def score_bot(db: Session, symbol: str, refresh_real_data: bool = True) -> BotMessage:
    if refresh_real_data:
        refresh_symbol_with_real_market_data(db, symbol)
    score = opportunity_score(db, symbol)
    lines = [f"{score['symbol']}: {score['score']}/100 - {score['label']}"]
    for factor in score["factors"][:5]:
        sign = "+" if factor["impact"] >= 0 else ""
        lines.append(f"- {factor['name']} ({sign}{factor['impact']}): {factor['evidence']}")
    return BotMessage("Score", "\n".join(lines))


def explanation_bot(db: Session, symbol: str, refresh_real_data: bool = True) -> BotMessage:
    if refresh_real_data:
        refresh_symbol_with_real_market_data(db, symbol)
    explanation = movement_explanation(db, symbol)
    lines = [f"Explicacao verificavel para {explanation['symbol']}"]
    lines.append("\nFatos:")
    lines.extend(f"- {item}" for item in explanation["facts"])
    lines.append("\nEventos relacionados:")
    lines.extend(f"- {item}" for item in explanation["related_events"][:5])
    lines.append("\nHipoteses:")
    lines.extend(f"- {item}" for item in explanation["hypotheses"])
    return BotMessage("Explicacao", "\n".join(lines))


def review_bot(db: Session) -> BotMessage:
    brief = weekly_brief(db)
    quality = signal_quality(db)
    lines = ["Revisao do copiloto:"]
    lines.extend(f"- {item}" for item in brief["summary"])
    if quality:
        lines.append("\nSinais mais ruidosos:")
        lines.extend(f"- {row['symbol']}: ruido {row['noise_score']} ({row['assessment']})" for row in quality[:5])
    if brief["risks"]:
        lines.append("\nRiscos a revisar:")
        lines.extend(f"- {row['symbol']}: {row['score']}/100 - {row['label']}" for row in brief["risks"])
    return BotMessage("Revisao", "\n".join(lines))


def decision_prompt_bot(symbol: str) -> BotMessage:
    symbol = symbol.upper().strip()
    return BotMessage(
        "Decisao",
        "\n".join(
            [
                f"Antes de agir em {symbol}, registre:",
                "1. Tese: por que esse ativo?",
                "2. Gatilho: o que precisa acontecer?",
                "3. Invalidacao: o que prova que voce estava errado?",
                "4. Prazo: intraday, swing, pos-earnings?",
                "5. Risco: quanto pode perder se estiver errado?",
                "",
                f"Use: /decisao {symbol} | tese | gatilho | invalidacao | prazo | risco",
            ]
        ),
    )
