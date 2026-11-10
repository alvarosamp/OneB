from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from statistics import mean

import pandas as pd
from sqlalchemy.orm import Session

from app import indicators
from app.market_data import yfinance_client
from app.scope import active_watchlist, latest_snapshot_for_symbol
from app.models import AlertLog, EarningsEvent, EconomicEvent, GlobalNewsItem, NewsItem, PriceSnapshot, Transaction, TransactionSide, WatchlistItem
from app.positions import compute_position
from app.trader_profile import analyze_trader_profile


@dataclass
class AgentVote:
    name: str
    vote: str
    confidence: int
    summary: str
    evidence: list[str]


def _latest_snapshot(db: Session, symbol: str) -> PriceSnapshot | None:
    return latest_snapshot_for_symbol(db, symbol)  # dado de mercado compartilhado


def _vote_from_score(score: int) -> str:
    if score >= 65:
        return "Comprar"
    if score <= 35:
        return "Evitar"
    return "Neutro"


def _safe_last(series: pd.Series) -> float | None:
    clean = series.dropna()
    return float(clean.iloc[-1]) if not clean.empty else None


def technical_agent(symbol: str, history: pd.DataFrame, snapshot: PriceSnapshot | None) -> AgentVote:
    if history.empty:
        return AgentVote("Tecnico", "Neutro", 10, "Sem historico suficiente para analise tecnica.", [],)

    close = history["close"]
    ema9 = _safe_last(indicators.ema(close, 9))
    ema21 = _safe_last(indicators.ema(close, 21))
    rsi = _safe_last(indicators.rsi(close))
    macd_df = indicators.macd(close)
    macd = _safe_last(macd_df["macd"])
    signal = _safe_last(macd_df["signal"])
    volume_ratio = _safe_last(indicators.volume_ratio(history["volume"]))
    last_price = float(close.iloc[-1])
    day_change = snapshot.change_pct if snapshot else float(close.pct_change().iloc[-1] * 100)

    score = 50
    evidence = []
    if ema9 and ema21:
        if ema9 > ema21:
            score += 14
            evidence.append("EMA9 acima da EMA21 indica tendencia curta positiva.")
        else:
            score -= 14
            evidence.append("EMA9 abaixo da EMA21 indica perda de forca curta.")
    if rsi is not None:
        if 45 <= rsi <= 68:
            score += 10
            evidence.append(f"RSI em {rsi:.1f}, zona saudavel de momentum.")
        elif rsi > 75:
            score -= 8
            evidence.append(f"RSI em {rsi:.1f}, possivel sobrecompra.")
        elif rsi < 35:
            score -= 6
            evidence.append(f"RSI em {rsi:.1f}, ativo ainda fragil ou em sobrevenda.")
    if macd is not None and signal is not None:
        if macd > signal:
            score += 10
            evidence.append("MACD acima do sinal confirma momentum.")
        else:
            score -= 8
            evidence.append("MACD abaixo do sinal pede cautela.")
    if volume_ratio and volume_ratio > 1.4:
        score += 8
        evidence.append(f"Volume {volume_ratio:.1f}x acima da media recente.")
    if day_change > 2:
        score += 6
        evidence.append(f"Alta intraday de {day_change:.2f}%.")
    elif day_change < -2:
        score -= 8
        evidence.append(f"Queda intraday de {day_change:.2f}%.")

    score = max(0, min(100, score))
    return AgentVote(
        "Tecnico",
        _vote_from_score(score),
        score,
        f"{symbol} esta em {last_price:.2f}; leitura tecnica {_vote_from_score(score).lower()}.",
        evidence[:5],
    )


def news_agent(db: Session, symbol: str, user_id: int | None = None) -> AgentVote:
    news = db.query(NewsItem).filter(NewsItem.symbol == symbol).order_by(NewsItem.published_at.desc()).limit(12).all()
    alert_query = db.query(AlertLog).filter(AlertLog.symbol == symbol)
    if user_id is not None:
        alert_query = alert_query.filter(AlertLog.user_id == user_id)
    alerts = alert_query.order_by(AlertLog.triggered_at.desc()).limit(6).all()
    score = 45 + min(len(news) * 5, 25) + min(len(alerts) * 4, 16)
    negative_terms = ["lawsuit", "probe", "investigation", "miss", "cuts", "downgrade", "fraud", "recall"]
    positive_terms = ["beats", "raises", "upgrade", "partnership", "growth", "record", "approval"]
    headlines = " ".join(n.headline.lower() for n in news)
    score += sum(8 for term in positive_terms if term in headlines)
    score -= sum(12 for term in negative_terms if term in headlines)
    score = max(0, min(100, score))

    evidence = [n.headline for n in news[:4]]
    if alerts:
        evidence.append(f"{len(alerts)} alerta(s) recente(s) no sistema.")
    return AgentVote(
        "Noticias",
        _vote_from_score(score),
        score,
        f"{len(news)} noticia(s) recentes e {len(alerts)} alerta(s) para {symbol}.",
        evidence,
    )


def macro_agent(db: Session) -> AgentVote:
    global_news = db.query(GlobalNewsItem).order_by(GlobalNewsItem.impact_score.desc(), GlobalNewsItem.published_at.desc()).limit(8).all()
    high_events = db.query(EconomicEvent).filter(EconomicEvent.impact == "high").order_by(EconomicEvent.event_date).limit(5).all()
    score = 55
    if global_news:
        avg_impact = mean([n.impact_score for n in global_news])
        score -= min(20, int(avg_impact / 5))
    if high_events:
        score -= min(15, len(high_events) * 3)
    score = max(0, min(100, score))
    evidence = [f"{n.headline} (impacto {n.impact_score})" for n in global_news[:4]]
    evidence.extend(f"{e.event_name} ({e.country})" for e in high_events[:3])
    return AgentVote("Macro", _vote_from_score(score), score, "Leitura macro baseada em noticias globais e calendario economico.", evidence)


def risk_agent(db: Session, symbol: str, capital_usd: float, risk_budget_pct: float, entry_price: float | None, history: pd.DataFrame, user_id: int | None = None) -> AgentVote:
    tx_query = db.query(Transaction).filter(Transaction.symbol == symbol)
    if user_id is not None:
        tx_query = tx_query.filter(Transaction.user_id == user_id)
    transactions = tx_query.all()
    position = compute_position(symbol, transactions, entry_price)
    close = history["close"].dropna() if not history.empty else pd.Series(dtype=float)
    volatility = float(close.pct_change().dropna().tail(20).std() * 100) if len(close) > 20 else 0.0
    stop_pct = max(2.0, min(10.0, volatility * 2 if volatility else 4.0))
    risk_amount = capital_usd * (risk_budget_pct / 100)
    stop_distance = (entry_price or 0) * (stop_pct / 100)
    quantity = int(risk_amount / stop_distance) if stop_distance > 0 else 0
    score = 70
    if volatility > 4:
        score -= 18
    if position.quantity > 0:
        score -= 8
    if risk_budget_pct > 2:
        score -= 12
    evidence = [
        f"Risco maximo informado: US$ {risk_amount:.2f}.",
        f"Stop tecnico estimado: {stop_pct:.2f}% abaixo da entrada.",
        f"Tamanho sugerido por risco: {quantity} unidade(s).",
    ]
    if position.quantity:
        evidence.append(f"Ja existe posicao de {position.quantity} em {symbol}.")
    return AgentVote("Risco", _vote_from_score(max(0, min(100, score))), max(0, min(100, score)), "Gestao de risco calculada por capital, stop e volatilidade.", evidence)


def profile_agent(db: Session, symbol: str, user_id: int | None = None) -> AgentVote:
    profile = analyze_trader_profile(db, user_id)
    summary = profile["summary"]
    tx_query = db.query(Transaction)
    if user_id is not None:
        tx_query = tx_query.filter(Transaction.user_id == user_id)
    transactions = tx_query.order_by(Transaction.executed_at).all()
    if summary["closed_trades"] < 3:
        return AgentVote("Perfil", "Neutro", 45, "Ainda ha poucas operacoes registradas para aprender o perfil do trader.", ["Registre mais compras e vendas para gerar diagnosticos pessoais."])
    tech_count = sum(1 for tx in transactions if tx.symbol in {"NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA"})
    symbol_count = sum(1 for tx in transactions if tx.symbol == symbol)
    evidence = [
        f"{summary['closed_trades']} operacao(oes) fechadas; taxa de acerto {summary['win_rate']}%.",
        f"Expectativa media por trade: US$ {summary['expectancy']:.2f}.",
        f"{symbol_count} transacao(oes) historicas em {symbol}.",
    ]
    evidence.extend(profile["insights"][:2])
    if tech_count / len(transactions) > 0.6:
        evidence.append("Historico concentrado em tecnologia; cuidado com correlacao setorial.")
    score = 60 if summary["expectancy"] > 0 and summary["profit_factor"] >= 1 else 45
    return AgentVote("Perfil", _vote_from_score(score), score, "Perfil analisado a partir do diario inteligente de transacoes.", evidence)


def simulate_history(history: pd.DataFrame) -> dict:
    close = history["close"].dropna() if not history.empty else pd.Series(dtype=float)
    if len(close) < 40:
        return {"available": False, "summary": "Historico insuficiente para simulacao.", "metrics": {}}
    returns = close.pct_change().dropna()
    total_return = (close.iloc[-1] / close.iloc[0] - 1) * 100
    rolling_max = close.cummax()
    drawdown = ((close / rolling_max) - 1) * 100
    avg = returns.mean()
    std = returns.std()
    sharpe = (avg / std) * sqrt(252) if std else 0.0
    downside = returns[returns < 0].std()
    sortino = (avg / downside) * sqrt(252) if downside else 0.0
    win_rate = (returns > 0).mean() * 100
    def clean(value: float, decimals: int = 2) -> float:
        return round(float(value), decimals) if isfinite(float(value)) else 0.0

    metrics = {
        "retorno_periodo_pct": clean(total_return),
        "drawdown_max_pct": clean(drawdown.min()),
        "sharpe_aprox": clean(sharpe),
        "sortino_aprox": clean(sortino),
        "taxa_acerto_dias_pct": clean(win_rate),
        "expectativa_diaria_pct": clean(avg * 100, 3),
    }
    return {"available": True, "summary": "Simulacao buy-and-hold aproximada no periodo carregado.", "metrics": metrics}


def detect_patterns(db: Session, user_id: int | None = None) -> list[str]:
    items = active_watchlist(db, user_id)
    patterns = []
    for item in items:
        history = yfinance_client.get_history(item.symbol, period="3mo", interval="1d")
        if history.empty or len(history) < 30:
            continue
        close = history["close"]
        high_20 = close.tail(20).max()
        last = close.iloc[-1]
        ema9 = _safe_last(indicators.ema(close, 9))
        ema21 = _safe_last(indicators.ema(close, 21))
        if ema9 and ema21 and ema9 > ema21 and last >= high_20 * 0.98:
            patterns.append(f"{item.symbol}: tendencia positiva perto de rompimento de 20 dias.")
        rsi = _safe_last(indicators.rsi(close))
        if rsi and 45 <= rsi <= 60 and last > close.tail(10).mean():
            patterns.append(f"{item.symbol}: consolidacao com momentum saudavel.")
    return patterns[:12]


def analyze_symbol(
    db: Session, symbol: str, capital_usd: float, risk_budget_pct: float, question: str = "", user_id: int | None = None
) -> dict:
    symbol = symbol.upper().strip()
    history = yfinance_client.get_history(symbol, period="1y", interval="1d")
    snapshot = _latest_snapshot(db, symbol)
    entry_price = snapshot.price if snapshot else (float(history["close"].iloc[-1]) if not history.empty else None)
    agents = [
        technical_agent(symbol, history, snapshot),
        news_agent(db, symbol, user_id),
        macro_agent(db),
        risk_agent(db, symbol, capital_usd, risk_budget_pct, entry_price, history, user_id),
        profile_agent(db, symbol, user_id),
    ]
    confidence = round(mean([a.confidence for a in agents]))
    buy_votes = sum(1 for a in agents if a.vote == "Comprar")
    avoid_votes = sum(1 for a in agents if a.vote == "Evitar")
    if buy_votes >= 3 and confidence >= 60:
        bias = "OBSERVAR_COMPRA"
    elif avoid_votes >= 2 or confidence < 40:
        bias = "EVITAR_POR_ENQUANTO"
    else:
        bias = "AGUARDAR_CONFIRMACAO"

    risk_vote = next(a for a in agents if a.name == "Risco")
    explanation = [
        f"Estamos olhando {symbol} porque {buy_votes} de {len(agents)} agentes ficaram construtivos.",
        f"Confianca consolidada: {confidence}%.",
        "A decisao final deve validar entrada, stop, noticia recente e tamanho de posicao antes de qualquer ordem manual.",
    ]
    contrary = []
    for agent in agents:
        if agent.vote != "Comprar":
            contrary.extend(agent.evidence[:1])
    return {
        "symbol": symbol,
        "question": question,
        "bias": bias,
        "confidence": confidence,
        "entry_price": round(entry_price, 2) if entry_price else None,
        "votes": [agent.__dict__ for agent in agents],
        "why": explanation,
        "contrary_view": contrary[:5],
        "risk_plan": risk_vote.evidence,
        "simulation": simulate_history(history),
        "patterns": detect_patterns(db, user_id),
        "disclaimer": "Nao e recomendacao de investimento nem ordem de compra/venda. Use como copiloto de analise e valide manualmente.",
    }
