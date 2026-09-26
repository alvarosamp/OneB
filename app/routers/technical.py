import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import indicators, technical_edge
from app.audit import audit
from app.auth import get_current_user
from app.db import get_db
from app.market_data import service as market_data_service
from app.models import TechnicalLevel, TradeSetup
from app.saas import get_or_create_workspace
from app.schemas import (
    TechnicalAnalysisOut,
    TechnicalLevelCreate,
    TechnicalLevelOut,
    TradeSetupCreate,
    TradeSetupOut,
)

router = APIRouter(prefix="/api/technical", tags=["technical"], dependencies=[Depends(get_current_user)])


@router.get("/intraday-cards")
def intraday_cards():
    """Read the latest research snapshot; stale cards can never suggest action."""
    path = Path(__file__).resolve().parents[2] / "data" / "research" / "intraday_cards" / "latest.json"
    if not path.exists():
        return {"status": "UNAVAILABLE", "cards": [], "reason": "Snapshot intradiario ainda nao foi gerado."}
    payload = json.loads(path.read_text(encoding="utf-8"))
    for card in payload.get("cards", []):
        as_of = datetime.fromisoformat(card["as_of"])
        if datetime.now(timezone.utc) - as_of > timedelta(minutes=20):
            card["action"] = "NO_TRADE"
            card["direction"] = None
            card["entry_price"] = None
            card["stop_price"] = None
            card["take_profit"] = []
            card["confidence_pct"] = None
            card["data_health"]["fresh"] = False
            if "Snapshot desatualizado." not in card["reasons"]:
                card["reasons"].insert(0, "Snapshot desatualizado.")
    return payload


@router.get("/edge")
def technical_edge_ranking(
    symbols: str = "AAPL,MSFT,NVDA,AMD,AMZN,GOOGL,META,TSLA,AVGO,NFLX",
    period: str = "2y",
):
    """Research-only five-day cross-sectional ranking for a ticker list.

    It is intentionally an observation aid: ``OBSERVAR`` is not an order or
    investment recommendation, and the ranking is meaningful only inside the
    selected universe.
    """
    selected = list(dict.fromkeys(item.strip().upper() for item in symbols.split(",") if item.strip()))
    if len(selected) < 3:
        raise HTTPException(status_code=400, detail="Informe ao menos tres simbolos para formar um ranking")
    if len(selected) > 50:
        raise HTTPException(status_code=400, detail="Limite de 50 simbolos por ranking")
    benchmark = market_data_service.get_bars("QQQ", period=period, interval="1d")
    if benchmark.empty:
        raise HTTPException(status_code=503, detail="Sem historico do benchmark QQQ")
    histories = {symbol: market_data_service.get_bars(symbol, period=period, interval="1d") for symbol in selected}
    ranked = technical_edge.rank_latest(histories, benchmark)
    return {
        "horizon_days": technical_edge.HORIZON_DAYS,
        "benchmark": "QQQ",
        "universe": selected,
        "research_note": "Ranking experimental de observacao; nao e recomendacao nem ordem.",
        "rows": ranked,
    }


def _last(values):
    clean = [float(value) for value in values if value == value]
    return clean[-1] if clean else None


def _avg(values, size: int):
    clean = [float(value) for value in values[-size:] if value == value]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _workspace_filter(query, workspace_id: int | None):
    return query.filter((TechnicalLevel.workspace_id == workspace_id) | (TechnicalLevel.workspace_id.is_(None)))


def _setup_workspace_filter(query, workspace_id: int | None):
    return query.filter((TradeSetup.workspace_id == workspace_id) | (TradeSetup.workspace_id.is_(None)))


def _risk_reward(entry: float | None, stop: float | None, target: float | None):
    if entry is None or stop is None or target is None:
        return None
    risk = abs(entry - stop)
    reward = abs(target - entry)
    if risk == 0:
        return None
    return round(reward / risk, 2)


def _pct_distance(price: float | None, level: float | None):
    if price in (None, 0) or level is None:
        return None
    return round(((level - price) / price) * 100, 2)


def _volatility_label(atr_pct: float | None, annualized_volatility: float | None) -> str:
    if atr_pct is None and annualized_volatility is None:
        return "Sem leitura"
    if (atr_pct or 0) >= 5 or (annualized_volatility or 0) >= 80:
        return "Muito alta"
    if (atr_pct or 0) >= 3 or (annualized_volatility or 0) >= 50:
        return "Alta"
    if (atr_pct or 0) >= 1.5 or (annualized_volatility or 0) >= 25:
        return "Media"
    return "Baixa"


@router.get("/analysis/{symbol}", response_model=TechnicalAnalysisOut)
def technical_analysis(
    symbol: str,
    period: str = "5d",
    interval: str = "15m",
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    symbol = symbol.upper().strip()
    history = market_data_service.get_bars(symbol, period=period, interval=interval)
    if history.empty:
        raise HTTPException(status_code=404, detail="Sem dados historicos para este simbolo")

    close = history["close"]
    rsi_series = indicators.rsi(close)
    ema_fast = indicators.ema(close, 9)
    ema_slow = indicators.ema(close, 21)
    macd_df = indicators.macd(close)
    atr_series = indicators.atr(history["high"], history["low"], close)
    annualized_volatility_series = indicators.annualized_volatility(close)

    price = _last(close.tolist())
    previous = _last(close.iloc[:-1].tolist()) if len(close) > 1 else None
    change_pct = None if price is None or previous in (None, 0) else round(((price - previous) / previous) * 100, 2)
    support = round(float(history["low"].tail(80).min()), 2)
    resistance = round(float(history["high"].tail(80).max()), 2)
    pivot_value = _avg(close.tolist(), 20)
    pivot = round(pivot_value, 2) if pivot_value is not None else None
    rsi = _last(rsi_series.tolist())
    volume = _last(history["volume"].tolist())
    avg_volume_20 = _avg(history["volume"].tolist(), 20)
    atr_14 = _last(atr_series.tolist())
    annualized_volatility_20 = _last(annualized_volatility_series.tolist())
    avg_range_pct_20_value = _avg(((history["high"] - history["low"]) / close * 100).tolist(), 20)
    fast = _last(ema_fast.tolist())
    slow = _last(ema_slow.tolist())
    macd = _last(macd_df["macd"].tolist())
    macd_signal = _last(macd_df["signal"].tolist())
    atr_pct = None if price in (None, 0) or atr_14 is None else (atr_14 / price) * 100
    distance_to_support_pct = _pct_distance(price, support)
    distance_to_resistance_pct = _pct_distance(price, resistance)
    suggested_shares_200_usd = int(200 // price) if price else 0
    suggested_risk_usd_200 = (
        round((atr_14 or 0) * suggested_shares_200_usd, 2)
        if atr_14 is not None and suggested_shares_200_usd > 0
        else None
    )
    volatility_label = _volatility_label(atr_pct, annualized_volatility_20)

    signals = []
    if price is not None and fast is not None and slow is not None:
        if price > fast > slow:
            trend = "Tendencia de alta"
            bias = "ALTISTA"
            signals.append(
                {
                    "name": "medias",
                    "label": "Preco acima das medias",
                    "state": "good",
                    "evidence": "Preco acima da EMA9, e EMA9 acima da EMA21.",
                }
            )
        elif price < fast < slow:
            trend = "Tendencia de baixa"
            bias = "BAIXISTA"
            signals.append(
                {
                    "name": "medias",
                    "label": "Preco abaixo das medias",
                    "state": "danger",
                    "evidence": "Preco abaixo da EMA9, e EMA9 abaixo da EMA21.",
                }
            )
        else:
            trend = "Lateral ou virando mao"
            bias = "NEUTRO"
            signals.append(
                {
                    "name": "medias",
                    "label": "Medias emboladas",
                    "state": "warn",
                    "evidence": "Preco e medias ainda nao apontam uma direcao limpa.",
                }
            )
    else:
        trend = "Sem leitura suficiente"
        bias = "NEUTRO"

    if rsi is not None:
        if rsi >= 70:
            signals.append({"name": "rsi", "label": "RSI esticado", "state": "warn", "evidence": f"RSI em {rsi:.2f}."})
        elif rsi <= 30:
            signals.append({"name": "rsi", "label": "RSI sobrevendido", "state": "warn", "evidence": f"RSI em {rsi:.2f}."})
        else:
            signals.append({"name": "rsi", "label": "RSI saudavel", "state": "good", "evidence": f"RSI em {rsi:.2f}."})

    if volume is not None and avg_volume_20:
        volume_ratio = volume / avg_volume_20
        state = "good" if volume_ratio >= 1.2 else "warn" if volume_ratio < 0.7 else "neutral"
        signals.append(
            {
                "name": "volume",
                "label": "Volume relativo",
                "state": state,
                "evidence": f"Volume atual em {volume_ratio:.2f}x a media de 20 candles.",
            }
        )

    if macd is not None and macd_signal is not None:
        state = "good" if macd > macd_signal else "danger"
        signals.append(
            {
                "name": "macd",
                "label": "MACD acima do sinal" if macd > macd_signal else "MACD abaixo do sinal",
                "state": state,
                "evidence": f"MACD {macd:.3f} contra sinal {macd_signal:.3f}.",
            }
        )

    if atr_pct is not None:
        state = "danger" if volatility_label in {"Alta", "Muito alta"} else "warn" if volatility_label == "Media" else "good"
        signals.append(
            {
                "name": "volatilidade",
                "label": f"Volatilidade {volatility_label.lower()}",
                "state": state,
                "evidence": f"ATR14 em {atr_pct:.2f}% do preco; vol. anualizada 20 em {(annualized_volatility_20 or 0):.2f}%.",
            }
        )

    workspace = get_or_create_workspace(db, user)
    levels = (
        _workspace_filter(
            db.query(TechnicalLevel).filter(TechnicalLevel.symbol == symbol).filter(TechnicalLevel.active.is_(True)),
            workspace.id,
        )
        .order_by(TechnicalLevel.price.desc())
        .all()
    )
    setups = (
        _setup_workspace_filter(
            db.query(TradeSetup).filter(TradeSetup.symbol == symbol).filter(TradeSetup.status != "ARCHIVED"),
            workspace.id,
        )
        .order_by(TradeSetup.created_at.desc())
        .all()
    )
    latest_setup = setups[0] if setups else None

    return {
        "symbol": symbol,
        "price": round(price, 2) if price is not None else None,
        "change_pct": change_pct,
        "support": support,
        "resistance": resistance,
        "pivot": pivot,
        "rsi": round(rsi, 2) if rsi is not None else None,
        "volume": volume,
        "avg_volume_20": avg_volume_20,
        "atr_14": round(atr_14, 2) if atr_14 is not None else None,
        "atr_pct": round(atr_pct, 2) if atr_pct is not None else None,
        "annualized_volatility_20": round(annualized_volatility_20, 2) if annualized_volatility_20 is not None else None,
        "avg_range_pct_20": round(avg_range_pct_20_value, 2) if avg_range_pct_20_value is not None else None,
        "distance_to_support_pct": distance_to_support_pct,
        "distance_to_resistance_pct": distance_to_resistance_pct,
        "suggested_shares_200_usd": suggested_shares_200_usd,
        "suggested_risk_usd_200": suggested_risk_usd_200,
        "volatility_label": volatility_label,
        "trend": trend,
        "bias": bias,
        "risk_reward": _risk_reward(
            latest_setup.entry_price if latest_setup else None,
            latest_setup.stop_price if latest_setup else None,
            latest_setup.target_price if latest_setup else None,
        ),
        "signals": signals,
        "levels": levels,
        "setups": setups,
    }


@router.get("/levels/{symbol}", response_model=list[TechnicalLevelOut])
def list_levels(symbol: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    workspace = get_or_create_workspace(db, user)
    return (
        _workspace_filter(
            db.query(TechnicalLevel)
            .filter(TechnicalLevel.symbol == symbol.upper().strip())
            .filter(TechnicalLevel.active.is_(True)),
            workspace.id,
        )
        .order_by(TechnicalLevel.price.desc())
        .all()
    )


@router.post("/levels", response_model=TechnicalLevelOut, status_code=201)
def create_level(payload: TechnicalLevelCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    workspace = get_or_create_workspace(db, user)
    level = TechnicalLevel(
        user_id=getattr(user, "id", None),
        workspace_id=workspace.id,
        symbol=payload.symbol.upper().strip(),
        label=payload.label.strip() or payload.kind,
        kind=payload.kind.upper().strip(),
        price=payload.price,
        color=payload.color,
        notes=payload.notes,
    )
    db.add(level)
    audit(db, user, "technical.level.create", "technical_level", level.symbol, {"price": level.price})
    db.commit()
    db.refresh(level)
    return level


@router.delete("/levels/{level_id}", status_code=204)
def delete_level(level_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    workspace = get_or_create_workspace(db, user)
    level = db.get(TechnicalLevel, level_id)
    if not level or level.workspace_id not in (None, workspace.id):
        raise HTTPException(status_code=404, detail="Nivel nao encontrado")
    level.active = False
    audit(db, user, "technical.level.delete", "technical_level", level.id, {"symbol": level.symbol})
    db.commit()


@router.post("/setups", response_model=TradeSetupOut, status_code=201)
def create_setup(payload: TradeSetupCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    direction = payload.direction.upper().strip()
    if direction not in {"LONG", "SHORT"}:
        raise HTTPException(status_code=400, detail="Direcao precisa ser LONG ou SHORT")
    setup = TradeSetup(
        user_id=getattr(user, "id", None),
        workspace_id=get_or_create_workspace(db, user).id,
        symbol=payload.symbol.upper().strip(),
        direction=direction,
        entry_price=payload.entry_price,
        stop_price=payload.stop_price,
        target_price=payload.target_price,
        thesis=payload.thesis,
        invalidation=payload.invalidation,
    )
    db.add(setup)
    audit(db, user, "technical.setup.create", "trade_setup", setup.symbol, {"direction": setup.direction})
    db.commit()
    db.refresh(setup)
    return setup


@router.delete("/setups/{setup_id}", status_code=204)
def archive_setup(setup_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    workspace = get_or_create_workspace(db, user)
    setup = db.get(TradeSetup, setup_id)
    if not setup or setup.workspace_id not in (None, workspace.id):
        raise HTTPException(status_code=404, detail="Plano nao encontrado")
    setup.status = "ARCHIVED"
    audit(db, user, "technical.setup.archive", "trade_setup", setup.id, {"symbol": setup.symbol})
    db.commit()
