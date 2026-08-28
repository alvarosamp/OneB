from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app import llm_client
from app import paper_simulator as sim
from app import probability_model as pm
from app.config import settings
from app.data_quality import quality_gate
from app.decision_cards import build_decision_card
from app.market_data import finnhub_client
from app.models import RecommendationDecision, WatchlistItem
from app.predictions import Evidence, Prediction
from app.risk_engine import evaluate_decision
from app.saas import get_or_create_workspace

AI_NARRATIVE_ACTIONS = {"BUY_CONTROLLED", "WATCH_BUY", "SELL_SHORT", "WATCH_SHORT"}
LONG_ACTIONS = ("BUY_CONTROLLED", "WATCH_BUY")
SHORT_ACTIONS = ("SELL_SHORT", "WATCH_SHORT")


DEFAULT_DECISION_SYMBOLS = sim.DEFAULT_SYMBOLS

DECISION_MIN_SETUP_SCORE = int(os.getenv("DECISION_MIN_SETUP_SCORE", "66"))
DECISION_BUY_SCORE = int(os.getenv("DECISION_BUY_SCORE", "78"))
DECISION_MIN_VOLUME_RATIO = float(os.getenv("DECISION_MIN_VOLUME_RATIO", "1.0"))
DECISION_MAX_VOLATILITY = float(os.getenv("DECISION_MAX_VOLATILITY", "90"))
DECISION_STOP_ATR_MULTIPLIER = float(os.getenv("DECISION_STOP_ATR_MULTIPLIER", "1.2"))
DECISION_TARGET_ATR_MULTIPLIER = float(os.getenv("DECISION_TARGET_ATR_MULTIPLIER", "2.3"))
DECISION_WEAK_SCORE = int(os.getenv("DECISION_WEAK_SCORE", "50"))

# Short-side thresholds are deliberately separate, static constants — the
# walk-forward calibration (see effective_thresholds below) only ever
# validated the long-side strategy, so it has no business overriding these.
DECISION_SHORT_MIN_SETUP_SCORE = int(os.getenv("DECISION_SHORT_MIN_SETUP_SCORE", "66"))
DECISION_SHORT_SCORE = int(os.getenv("DECISION_SHORT_SCORE", "78"))
DECISION_SHORT_MIN_VOLUME_RATIO = float(os.getenv("DECISION_SHORT_MIN_VOLUME_RATIO", "1.0"))
DECISION_SHORT_MAX_VOLATILITY = float(os.getenv("DECISION_SHORT_MAX_VOLATILITY", "90"))
DECISION_SHORT_STOP_ATR_MULTIPLIER = float(os.getenv("DECISION_SHORT_STOP_ATR_MULTIPLIER", "1.2"))
DECISION_SHORT_TARGET_ATR_MULTIPLIER = float(os.getenv("DECISION_SHORT_TARGET_ATR_MULTIPLIER", "2.3"))
DECISION_SHORT_WEAK_SCORE = int(os.getenv("DECISION_SHORT_WEAK_SCORE", "50"))

PORTFOLIO_BREAKER_MIN_SAMPLES = int(os.getenv("DECISION_BREAKER_MIN_SAMPLES", "10"))
PORTFOLIO_BREAKER_WIN_RATE_PCT = float(os.getenv("DECISION_BREAKER_WIN_RATE_PCT", "40"))
PORTFOLIO_BREAKER_LOOKBACK = int(os.getenv("DECISION_BREAKER_LOOKBACK", "30"))

EARNINGS_BLACKOUT_DAYS = int(os.getenv("DECISION_EARNINGS_BLACKOUT_DAYS", "3"))

PROBABILITY_WIN_THRESHOLD = float(os.getenv("DECISION_PROBABILITY_WIN_THRESHOLD", "0.55"))
DECISION_QUALITY_MIN_CONFIDENCE = os.getenv("DECISION_QUALITY_MIN_CONFIDENCE", "MEDIUM").upper()

DECISION_CALIBRATION_PATH = Path(os.getenv("DECISION_CALIBRATION_PATH", "data/decision_strategy_calibration.json"))

_calibration_cache: object = "unloaded"


def reload_calibration() -> None:
    global _calibration_cache
    _calibration_cache = "unloaded"


def _static_thresholds() -> dict:
    return {
        "min_setup_score": DECISION_MIN_SETUP_SCORE,
        "buy_score": DECISION_BUY_SCORE,
        "min_volume_ratio": DECISION_MIN_VOLUME_RATIO,
        "max_volatility": DECISION_MAX_VOLATILITY,
        "stop_atr": DECISION_STOP_ATR_MULTIPLIER,
        "target_atr": DECISION_TARGET_ATR_MULTIPLIER,
        "weak_score": DECISION_WEAK_SCORE,
        "source": "static_default",
    }


def effective_thresholds() -> dict:
    """The live decision engine's actual operating thresholds.

    Prefers the latest walk-forward calibration
    (scripts/calibrate_decision_strategy.py, run weekly by
    app.scheduler.recalibrate_decision_strategy) over the static .env
    defaults above — but only when that calibration's own "best" config was
    marked reliable (positive walk-forward rank, at most one losing fold —
    see _walk_forward_rank there). Otherwise this falls back to the
    hand-picked static defaults instead of trading live on a config the
    walk-forward test itself flagged as not robust. Cached per process;
    call reload_calibration() after a fresh run to pick it up.
    """
    global _calibration_cache
    if _calibration_cache == "unloaded":
        data = None
        if DECISION_CALIBRATION_PATH.exists():
            try:
                data = json.loads(DECISION_CALIBRATION_PATH.read_text(encoding="utf-8"))
            except Exception:
                data = None
        best = (data or {}).get("best")
        if best and best.get("reliable"):
            params = best["params"]
            gap = DECISION_BUY_SCORE - DECISION_MIN_SETUP_SCORE
            min_setup = int(params["min_score"])
            _calibration_cache = {
                "min_setup_score": min_setup,
                "buy_score": min_setup + gap,
                "min_volume_ratio": float(params["min_volume_ratio"]),
                "max_volatility": float(params["max_volatility"]),
                "stop_atr": float(params["stop_atr"]),
                "target_atr": float(params["target_atr"]),
                "weak_score": int(params["weak_score"]),
                "source": "walk_forward_calibrated",
                "walk_forward_rank": best.get("walk_forward_rank"),
            }
        else:
            _calibration_cache = _static_thresholds()
    return _calibration_cache


SHORT_CALIBRATION_PATH = Path(os.getenv("SHORT_CALIBRATION_PATH", "data/short_strategy_calibration.json"))

_short_calibration_cache: object = "unloaded"


def reload_short_calibration() -> None:
    global _short_calibration_cache
    _short_calibration_cache = "unloaded"


def _static_short_thresholds() -> dict:
    return {
        "min_setup_score": DECISION_SHORT_MIN_SETUP_SCORE,
        "short_score": DECISION_SHORT_SCORE,
        "min_volume_ratio": DECISION_SHORT_MIN_VOLUME_RATIO,
        "max_volatility": DECISION_SHORT_MAX_VOLATILITY,
        "stop_atr": DECISION_SHORT_STOP_ATR_MULTIPLIER,
        "target_atr": DECISION_SHORT_TARGET_ATR_MULTIPLIER,
        "weak_score": DECISION_SHORT_WEAK_SCORE,
        "source": "static_default",
    }


def short_effective_thresholds() -> dict:
    """Mirror of effective_thresholds() for the short side — see
    scripts/backtest_short_strategy.py for the walk-forward calibration that
    produces SHORT_CALIBRATION_PATH. Same fail-safe: only overrides the
    static defaults when the walk-forward run marked its best config
    reliable (positive rank, at most one losing fold, survives the Deflated
    Sharpe Ratio check).
    """
    global _short_calibration_cache
    if _short_calibration_cache == "unloaded":
        data = None
        if SHORT_CALIBRATION_PATH.exists():
            try:
                data = json.loads(SHORT_CALIBRATION_PATH.read_text(encoding="utf-8"))
            except Exception:
                data = None
        best = (data or {}).get("best")
        if best and best.get("reliable"):
            params = best["params"]
            gap = DECISION_SHORT_SCORE - DECISION_SHORT_MIN_SETUP_SCORE
            min_setup = int(params["min_score"])
            _short_calibration_cache = {
                "min_setup_score": min_setup,
                "short_score": min_setup + gap,
                "min_volume_ratio": float(params["min_volume_ratio"]),
                "max_volatility": float(params["max_volatility"]),
                "stop_atr": float(params["stop_atr"]),
                "target_atr": float(params["target_atr"]),
                "weak_score": int(params["weak_score"]),
                "source": "walk_forward_calibrated",
                "walk_forward_rank": best.get("walk_forward_rank"),
            }
        else:
            _short_calibration_cache = _static_short_thresholds()
    return _short_calibration_cache


def _active_symbols(db: Session) -> list[str]:
    symbols = [item.symbol.upper() for item in db.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).all()]
    return sorted(set(symbols or DEFAULT_DECISION_SYMBOLS))


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(raw: str, fallback):
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def _last_price(history: pd.DataFrame) -> float:
    return float(history["close"].iloc[-1])


def _historical_memory(data: dict, benchmark: dict | None) -> dict:
    wins = 0
    false_positives = 0
    returns = []
    samples = 0
    for i in range(80, len(data["history"]) - 5):
        if not sim._indicators_ready(data, i):
            continue
        score, details = sim._opportunity_score(data, i, benchmark)
        if details["market"]["state"] == "risk_off" or score < DECISION_MIN_SETUP_SCORE or not sim._buy_base(data, i):
            continue
        price = float(data["history"]["close"].iloc[i])
        forward = (float(data["history"]["close"].iloc[i + 5]) / price - 1) * 100
        samples += 1
        returns.append(forward)
        if forward > 0.5:
            wins += 1
        else:
            false_positives += 1
    return {
        "historical_samples": samples,
        "historical_win_rate_pct": round(wins / samples * 100, 2) if samples else 0,
        "historical_false_positive_rate_pct": round(false_positives / samples * 100, 2) if samples else 0,
        "historical_avg_5d_return_pct": round(sum(returns) / samples, 2) if samples else 0,
    }


def _historical_memory_short(data: dict, benchmark: dict | None) -> dict:
    """Mirror of _historical_memory for the short side: a "win" is the price
    falling more than 0.5% over the next 5 sessions after a _sell_base
    trigger, instead of rising."""
    wins = 0
    false_positives = 0
    returns = []
    samples = 0
    for i in range(80, len(data["history"]) - 5):
        if not sim._indicators_ready(data, i):
            continue
        score, details = _bearish_score(data, i, benchmark)
        if score < DECISION_SHORT_MIN_SETUP_SCORE or not sim._sell_base(data, i):
            continue
        price = float(data["history"]["close"].iloc[i])
        forward = (float(data["history"]["close"].iloc[i + 5]) / price - 1) * 100
        samples += 1
        returns.append(forward)
        if forward < -0.5:
            wins += 1
        else:
            false_positives += 1
    return {
        "historical_samples": samples,
        "historical_win_rate_pct": round(wins / samples * 100, 2) if samples else 0,
        "historical_false_positive_rate_pct": round(false_positives / samples * 100, 2) if samples else 0,
        "historical_avg_5d_return_pct": round(sum(returns) / samples, 2) if samples else 0,
    }


def _logged_memory(db: Session, symbol: str, user_id: int | None, actions: tuple[str, ...] = LONG_ACTIONS) -> dict:
    query = db.query(RecommendationDecision).filter(
        RecommendationDecision.symbol == symbol,
        RecommendationDecision.action.in_(actions),
        RecommendationDecision.outcome_status != "PENDING",
    )
    if user_id is not None:
        query = query.filter((RecommendationDecision.user_id == user_id) | (RecommendationDecision.user_id.is_(None)))
    rows = query.order_by(RecommendationDecision.created_at.desc()).limit(50).all()
    wins = [row for row in rows if row.outcome_status == "HIT"]
    losses = [row for row in rows if row.outcome_status == "FALSE_POSITIVE"]
    returns = [float(row.outcome_return_5d_pct or 0) for row in rows if row.outcome_return_5d_pct is not None]
    return {
        "logged_samples": len(rows),
        "logged_win_rate_pct": round(len(wins) / len(rows) * 100, 2) if rows else 0,
        "logged_false_positive_rate_pct": round(len(losses) / len(rows) * 100, 2) if rows else 0,
        "logged_avg_5d_return_pct": round(sum(returns) / len(returns), 2) if returns else 0,
    }


def evaluate_pending_outcomes(db: Session) -> int:
    rows = (
        db.query(RecommendationDecision)
        .filter(
            (RecommendationDecision.outcome_status == "PENDING")
            | (RecommendationDecision.outcome_return_1d_pct.is_(None))
            | (RecommendationDecision.outcome_return_20d_pct.is_(None))
        )
        .all()
    )
    updated = 0
    for row in rows:
        history = sim._history(row.symbol)
        if history.empty:
            continue
        if not isinstance(history.index, pd.DatetimeIndex):
            continue
        decision_at = pd.Timestamp(row.created_at)
        decision_at = decision_at.tz_localize(None) if decision_at.tzinfo else decision_at
        index = history.index.tz_localize(None) if history.index.tz is not None else history.index
        start = next((i for i, stamp in enumerate(index) if stamp.normalize() >= decision_at.normalize()), None)
        if start is None:
            continue

        def observed_return(horizon: int) -> float | None:
            target = start + horizon
            if target >= len(history):
                return None
            raw = (float(history["close"].iloc[target]) / float(row.price) - 1) * 100
            return round(-raw if row.action in SHORT_ACTIONS else raw, 4)

        now = datetime.now(timezone.utc)
        one_day, five_day, twenty_day = observed_return(1), observed_return(5), observed_return(20)
        if one_day is not None and row.outcome_return_1d_pct is None:
            row.outcome_return_1d_pct, row.outcome_1d_checked_at = one_day, now
            updated += 1
        if five_day is not None and row.outcome_return_5d_pct is None:
            row.outcome_return_5d_pct = five_day
            row.outcome_status = "HIT" if five_day > 0.5 else "FALSE_POSITIVE"
            row.outcome_checked_at = now
            updated += 1
        if twenty_day is not None and row.outcome_return_20d_pct is None:
            row.outcome_return_20d_pct, row.outcome_20d_checked_at = twenty_day, now
            updated += 1
    if updated:
        db.commit()
    return updated


def _bearish_score(data: dict, i: int, benchmark: dict | None) -> tuple[int, dict]:
    """Mirror of sim._opportunity_score, scoring weakness instead of strength
    for downside (SELL_SHORT) setups: price below its moving averages,
    falling EMAs, relative underperformance vs the benchmark, and a market
    regime that's cooling off — same building blocks, opposite direction.
    Only used for advisory recommendations here; the paper-trading engine's
    actual capital (app.paper_simulator) stays long-only.
    """
    if not sim._indicators_ready(data, i):
        return 0, {"reason": "indicators_not_ready"}
    price = float(data["history"]["close"].iloc[i])
    atr = float(data["atr"].iloc[i])
    atr_pct = atr / price * 100
    trend = 0
    if price < float(data["sma20"].iloc[i]):
        trend += 6
    if price < float(data["sma50"].iloc[i]):
        trend += 8
    if float(data["ema9"].iloc[i]) < float(data["ema21"].iloc[i]):
        trend += 6
    if price < float(data["recent_low20"].iloc[i]):
        trend += 5

    volume = min(15, max(0, int((float(data["volume_ratio"].iloc[i]) - 0.8) * 18)))
    relative = 10
    if benchmark is not None and i < len(benchmark["history"]) and not pd.isna(benchmark["return20"].iloc[i]):
        # Underperformance vs the benchmark is the bearish signal here — flipped
        # sign from _opportunity_score's "relative strength".
        relative_weakness = float(benchmark["return20"].iloc[i]) - float(data["return20"].iloc[i])
        relative = min(20, max(0, int(10 + relative_weakness * 1.4)))

    risk_reward = 20 if 0.8 <= atr_pct <= 4 else 12 if atr_pct <= 6 else 5
    rsi = float(data["rsi"].iloc[i])
    if rsi < 28:
        risk_reward -= 6  # already oversold, chasing the short is riskier
    if rsi > 58:
        risk_reward -= 4
    risk_reward = max(0, risk_reward)

    market = sim._market_regime(benchmark, i)
    # Weakness in the broader market helps a short thesis — invert the same
    # 0-40ish market score _opportunity_score rewards for a long.
    market_bear_score = max(0, 25 - market["score"])
    score = min(100, trend + volume + relative + risk_reward + market_bear_score)
    details = {
        "score": score,
        "trend": trend,
        "volume": volume,
        "relative_weakness": relative,
        "risk_reward": risk_reward,
        "market": market,
        "atr_pct": round(atr_pct, 2),
    }
    return score, details


def _upcoming_earnings(symbol: str) -> datetime | None:
    """Earliest earnings date within the blackout window, or None.

    Uses app.market_data.finnhub_client, which already swallows API/network
    failures and returns [] — so an unconfigured or unreachable Finnhub key
    silently disables this check instead of breaking the decision desk.
    """
    today = datetime.now(timezone.utc).date()
    entries = finnhub_client.get_earnings_calendar(
        today, today + timedelta(days=EARNINGS_BLACKOUT_DAYS), symbol=symbol
    )
    dates = [entry.event_date for entry in entries if entry.symbol == symbol]
    return min(dates) if dates else None


def _action_from_context(
    score: int,
    data: dict,
    benchmark: dict | None,
    memory: dict,
    thresholds: dict,
    earnings_date: datetime | None = None,
    prob_win: float | None = None,
) -> tuple[str, int, list[str]]:
    i = len(data["history"]) - 1
    _, details = sim._opportunity_score(data, i, benchmark)
    reasons = []
    confidence = score
    if details["market"]["state"] == "risk_off":
        return "AVOID", min(confidence, 45), ["Mercado de referência em modo defensivo."]
    if not sim._buy_base(data, i):
        return "WAIT", min(confidence, 58), ["Tendência técnica ainda não confirmou compra."]
    if float(data["volume_ratio"].iloc[i]) < thresholds["min_volume_ratio"]:
        return "WAIT", min(confidence, 60), ["Volume relativo abaixo do ponto calibrado para entrada."]
    if float(data["annualized_volatility"].iloc[i]) > thresholds["max_volatility"]:
        return "WAIT", min(confidence, 60), ["Volatilidade anualizada muito alta para entrada limpa."]
    if memory["historical_samples"] >= 8 and memory["historical_win_rate_pct"] < 45:
        return "WAIT", min(confidence, 62), ["Histórico recente desse padrão tem falsos positivos demais."]
    if score >= thresholds["buy_score"] and memory["historical_avg_5d_return_pct"] > 0:
        if earnings_date is not None:
            return (
                "WATCH_BUY",
                min(65, confidence),
                [
                    f"Setup de compra confirmado, mas earnings em {earnings_date.date()} "
                    f"(dentro de {EARNINGS_BLACKOUT_DAYS} dias) trava o tamanho até passar o evento."
                ],
            )
        if prob_win is not None and prob_win < PROBABILITY_WIN_THRESHOLD:
            return (
                "WATCH_BUY",
                min(70, confidence),
                [
                    f"Regras confirmam compra, mas o modelo probabilístico estima só "
                    f"{prob_win * 100:.0f}% de chance de ganho (mínimo {PROBABILITY_WIN_THRESHOLD * 100:.0f}%) "
                    "— trava o tamanho até os dois concordarem."
                ],
            )
        reasons.append("Score alto com retorno médio histórico positivo.")
        if prob_win is not None:
            reasons.append(f"Modelo probabilístico concorda: {prob_win * 100:.0f}% de chance estimada de ganho.")
        return "BUY_CONTROLLED", min(95, confidence), reasons
    if score >= thresholds["min_setup_score"]:
        return "WATCH_BUY", min(74, confidence), ["Setup interessante, mas ainda precisa de confirmação."]
    return "WAIT", min(55, confidence), ["Score abaixo do mínimo para recomendação operacional."]


def _short_action_from_context(
    score: int,
    data: dict,
    benchmark: dict | None,
    memory: dict,
    thresholds: dict,
    earnings_date: datetime | None = None,
    prob_fall: float | None = None,
) -> tuple[str, int, list[str]]:
    """Mirror of _action_from_context for the short side. Note: risk_off is
    NOT an auto-AVOID here like it is for longs — a defensive market regime
    is, if anything, supportive of a bearish thesis, so that gate is simply
    absent rather than inverted into an auto-approval (still requires every
    other confirmation below)."""
    i = len(data["history"]) - 1
    confidence = score
    if not sim._sell_base(data, i):
        return "WAIT", min(confidence, 58), ["Tendência técnica ainda não confirmou baixa."]
    if float(data["volume_ratio"].iloc[i]) < thresholds["min_volume_ratio"]:
        return "WAIT", min(confidence, 60), ["Volume relativo abaixo do ponto calibrado para entrada vendida."]
    if float(data["annualized_volatility"].iloc[i]) > thresholds["max_volatility"]:
        return "WAIT", min(confidence, 60), ["Volatilidade anualizada muito alta para entrada vendida limpa."]
    if memory["historical_samples"] >= 8 and memory["historical_win_rate_pct"] < 45:
        return "WAIT", min(confidence, 62), ["Histórico recente desse padrão de queda tem falsos positivos demais."]
    if score >= thresholds["short_score"] and memory["historical_avg_5d_return_pct"] < 0:
        if earnings_date is not None:
            return (
                "WATCH_SHORT",
                min(65, confidence),
                [
                    f"Setup de venda confirmado, mas earnings em {earnings_date.date()} "
                    f"(dentro de {EARNINGS_BLACKOUT_DAYS} dias) trava o tamanho até passar o evento."
                ],
            )
        if prob_fall is not None and prob_fall < PROBABILITY_WIN_THRESHOLD:
            return (
                "WATCH_SHORT",
                min(70, confidence),
                [
                    f"Regras confirmam venda, mas o modelo probabilístico (invertido) estima só "
                    f"{prob_fall * 100:.0f}% de chance de queda (mínimo {PROBABILITY_WIN_THRESHOLD * 100:.0f}%) "
                    "— trava o tamanho até os dois concordarem."
                ],
            )
        reasons = ["Score alto com retorno médio histórico negativo (queda)."]
        if prob_fall is not None:
            reasons.append(f"Modelo probabilístico (invertido) concorda: {prob_fall * 100:.0f}% de chance estimada de queda.")
        return "SELL_SHORT", min(95, confidence), reasons
    if score >= thresholds["min_setup_score"]:
        return "WATCH_SHORT", min(74, confidence), ["Setup de queda interessante, mas ainda precisa de confirmação."]
    return "WAIT", min(55, confidence), ["Score de queda abaixo do mínimo para recomendação operacional."]


def _position_size_pct(action: str, confidence: int, market_state: str, prob_win: float | None) -> float:
    """Sizes the position with the model's own conviction instead of a flat
    bucket by confidence — more edge above the minimum bar, more capital at
    risk, capped either way. Falls back to the old confidence/market buckets
    when no probability model is loaded (fail-open, same as everywhere else
    this model is used).

    For SELL_SHORT, `prob_win` is expected to already be the model's P(fall)
    (the caller passes 1 - P(rise) — see _recommendation) so the same edge
    formula applies unchanged in both directions.
    """
    if action in ("WATCH_BUY", "WATCH_SHORT"):
        return 5.0
    if action not in ("BUY_CONTROLLED", "SELL_SHORT"):
        return 0.0
    if prob_win is not None:
        edge = prob_win - PROBABILITY_WIN_THRESHOLD
        return round(min(20.0, max(5.0, 8.0 + edge * 200.0)), 1)
    return 10.0 if confidence < 82 else 15.0 if market_state == "neutral" else 20.0


def _recommendation(
    symbol: str,
    data: dict,
    benchmark: dict | None,
    db: Session,
    user_id: int | None,
    thresholds: dict,
    short_thresholds: dict,
) -> dict:
    i = len(data["history"]) - 1
    price = _last_price(data["history"])
    atr = float(data["atr"].iloc[i])
    earnings_date = _upcoming_earnings(symbol)
    model = pm.get_model()
    features = sim.feature_vector(data, i, benchmark)
    # The model was only ever trained to estimate P(price rises) — for a
    # short setup its complement (1 - P(rise)) doubles as a rough P(falls),
    # not a separately fitted estimate, but it's a legitimate reuse: the two
    # events are complementary by construction.
    prob_rise = pm.predict_proba(model, features) if model and features is not None else None

    # ema9/macd crossover conditions in _buy_base/_sell_base are mutually
    # exclusive by construction, so at most one of these is ever true —
    # a symbol with no clear trend just falls through to plain WAIT below.
    is_short = sim._sell_base(data, i) and not sim._buy_base(data, i)

    if is_short:
        score, details = _bearish_score(data, i, benchmark)
        historical = _historical_memory_short(data, benchmark)
        logged = _logged_memory(db, symbol, user_id, actions=SHORT_ACTIONS)
        memory = {**historical, **logged}
        prob_directional = (1 - prob_rise) if prob_rise is not None else None
        action, confidence, action_reasons = _short_action_from_context(
            score, data, benchmark, memory, short_thresholds, earnings_date, prob_directional
        )
        stop_atr, target_atr, weak_score = (
            short_thresholds["stop_atr"],
            short_thresholds["target_atr"],
            short_thresholds["weak_score"],
        )
        calibration_label = short_thresholds["source"]
        thresholds_display = short_thresholds
    else:
        score, details = sim._opportunity_score(data, i, benchmark)
        historical = _historical_memory(data, benchmark)
        logged = _logged_memory(db, symbol, user_id, actions=LONG_ACTIONS)
        memory = {**historical, **logged}
        prob_directional = prob_rise
        action, confidence, action_reasons = _action_from_context(
            score, data, benchmark, memory, thresholds, earnings_date, prob_directional
        )
        stop_atr, target_atr, weak_score = thresholds["stop_atr"], thresholds["target_atr"], thresholds["weak_score"]
        calibration_label = thresholds["source"]
        thresholds_display = thresholds

    market = details["market"]
    gate = quality_gate(db, symbol, min_confidence=DECISION_QUALITY_MIN_CONFIDENCE)
    if not gate["allowed"]:
        action = "NO_TRADE"
        confidence = min(confidence, 35)
        action_reasons = [f"Quality gate bloqueou a decisao: {gate['reason']}."]
        prob_directional = None
    size = _position_size_pct(action, confidence, market["state"], prob_directional)
    relative_value = details.get("relative_strength", details.get("relative_weakness", 0))
    evidence = [
        f"Score {score}/100: tendência {details['trend']}, volume {details['volume']}, força relativa {relative_value}.",
        f"Mercado {market['state']} via {sim.BENCHMARK_SYMBOL}; multiplicador de risco {market['risk_multiplier']}.",
        f"Memória histórica: {historical['historical_samples']} casos, {historical['historical_win_rate_pct']}% de acerto, retorno médio 5d {historical['historical_avg_5d_return_pct']}%.",
        f"Calibração ativa ({calibration_label}): score mínimo {thresholds_display['min_setup_score']}, volume relativo "
        f"{thresholds_display['min_volume_ratio']}, volatilidade máxima {thresholds_display['max_volatility']}%, "
        f"stop {stop_atr} ATR e alvo {target_atr} ATR.",
    ]
    if gate.get("reason"):
        evidence.insert(0, f"Quality gate: {gate['reason']} ({gate['confidence']}).")
    if logged["logged_samples"]:
        evidence.append(
            f"Memória registrada: {logged['logged_samples']} recomendações, {logged['logged_win_rate_pct']}% de acerto."
        )
    if earnings_date is not None:
        evidence.append(f"Earnings em {earnings_date.date()} — dentro da janela de cautela de {EARNINGS_BLACKOUT_DAYS} dias.")
    if prob_directional is not None:
        label = "queda" if is_short else "ganho"
        evidence.append(
            f"Modelo probabilístico{' (invertido)' if is_short else ''}: {prob_directional * 100:.0f}% de chance "
            f"estimada de {label} (limiar {PROBABILITY_WIN_THRESHOLD * 100:.0f}%)."
        )
    fair_reason = " ".join(action_reasons + evidence[:2])
    thesis = (
        f"{symbol} tem leitura {action}: preço {price:.2f}, score {score}/100, "
        f"mercado {market['state']} e volatilidade anualizada {float(data['annualized_volatility'].iloc[i]):.2f}%."
    )
    actionable = action in AI_NARRATIVE_ACTIONS
    if is_short:
        stop_price = round(price + atr * stop_atr, 2) if actionable else None
        target_price = round(price - atr * target_atr, 2) if actionable else None
        invalidation = f"Perde força se subir acima de {price + atr * stop_atr:.2f} ou se o score voltar abaixo de {weak_score}."
    else:
        stop_price = round(price - atr * stop_atr, 2) if actionable else None
        target_price = round(price + atr * target_atr, 2) if actionable else None
        invalidation = f"Perde força se cair abaixo de {price - atr * stop_atr:.2f} ou se o score voltar abaixo de {weak_score}."
    prediction = Prediction(
        symbol=symbol,
        horizon="5d",
        direction="short" if is_short else "long",
        action=action,
        probability=prob_directional,
        confidence=round(confidence / 100, 4),
        uncertainty=round(1 - (confidence / 100), 4),
        regime=market["state"],
        model_id="decision_engine",
        model_version="v1",
        dataset_version="live",
        quality_score={"LOW": 0.25, "MEDIUM": 0.65, "HIGH": 0.95}.get(gate["confidence"], 0.0),
        data_as_of=data["history"].index[i].to_pydatetime(),
        evidence=[
            Evidence("technical", "bearish" if is_short else "bullish", min(score / 100, 1), confidence / 100, evidence[0]),
            Evidence("data_quality", "neutral" if gate["allowed"] else "bearish", 0.0 if gate["allowed"] else 1.0, 0.95, gate["reason"] or "OK"),
        ],
    )
    row = {
        "symbol": symbol,
        "action": action,
        "direction": "short" if is_short else "long",
        "confidence": int(confidence),
        "score": int(score),
        "price": round(price, 2),
        "suggested_size_pct": size,
        "stop_price": stop_price,
        "target_price": target_price,
        "thesis": thesis,
        "fair_reason": fair_reason,
        "invalidation": invalidation,
        "evidence": evidence,
        "memory": memory,
        "score_details": details,
        "ai_narrative": None,
        "probability_win_pct": round(prob_directional * 100, 1) if prob_directional is not None else None,
        "quality_gate": gate,
        "prediction": prediction.to_dict(),
    }
    risk = evaluate_decision(
        db,
        user_id=user_id,
        symbol=symbol,
        action=row["action"],
        suggested_size_pct=row["suggested_size_pct"],
        price=row["price"],
        quality_gate=gate,
    )
    if not risk.allowed and row["action"] not in {"WAIT", "AVOID", "NO_TRADE"}:
        row["action"] = "NO_TRADE"
        row["suggested_size_pct"] = 0.0
        row["confidence"] = min(row["confidence"], 35)
        row["fair_reason"] = "Risk engine bloqueou a decisão: " + "; ".join(risk.kill_switches)
        row["evidence"] = [f"Risk engine: {reason}" for reason in risk.reasons] + row["evidence"]
        prediction = Prediction(
            symbol=symbol,
            horizon="5d",
            direction=row["direction"],
            action=row["action"],
            probability=None,
            confidence=round(row["confidence"] / 100, 4),
            uncertainty=round(1 - (row["confidence"] / 100), 4),
            regime=market["state"],
            model_id="decision_engine",
            model_version="v1",
            dataset_version="live",
            quality_score={"LOW": 0.25, "MEDIUM": 0.65, "HIGH": 0.95}.get(gate["confidence"], 0.0),
            data_as_of=data["history"].index[i].to_pydatetime(),
            evidence=[
                Evidence("risk", "bearish", 1.0, 0.95, row["fair_reason"]),
            ],
        )
        row["prediction"] = prediction.to_dict()
        risk = evaluate_decision(
            db,
            user_id=user_id,
            symbol=symbol,
            action=row["action"],
            suggested_size_pct=row["suggested_size_pct"],
            price=row["price"],
            quality_gate=gate,
        )
    row["risk"] = risk.to_dict()
    row["decision_card"] = build_decision_card(row)
    return row


async def _attach_ai_narratives(rows: list[dict]) -> None:
    """Fills row["ai_narrative"] for the actionable rows, in place.

    Grounded only in the rule engine's own output (see generate_recommendation_thesis) —
    the LLM narrates the reading, it does not change action/confidence/stop/target.
    Best-effort: leaves ai_narrative as None on any failure or when no LLM is configured.
    """
    if not llm_client.is_configured():
        return
    targets = [row for row in rows if row["action"] in AI_NARRATIVE_ACTIONS]
    if not targets:
        return
    contexts = [
        {
            "symbol": row["symbol"],
            "action": row["action"],
            "confidence": row["confidence"],
            "score": row["score"],
            "price": row["price"],
            "stop_price": row["stop_price"],
            "target_price": row["target_price"],
            "thesis": row["thesis"],
            "fair_reason": row["fair_reason"],
            "invalidation": row["invalidation"],
            "memory": row["memory"],
        }
        for row in targets
    ]
    narratives = await asyncio.gather(
        *(llm_client.generate_recommendation_thesis(context) for context in contexts),
        return_exceptions=True,
    )
    for row, narrative in zip(targets, narratives):
        row["ai_narrative"] = narrative if isinstance(narrative, str) else None


def _portfolio_recent_performance(db: Session, user_id: int | None) -> dict:
    """The AI's own recent track record across ALL symbols (not one at a time).

    This is what the portfolio circuit breaker acts on — a per-symbol memory
    check (see _action_from_context) can miss a strategy that is failing
    broadly across the whole watchlist at once.
    """
    query = db.query(RecommendationDecision).filter(
        RecommendationDecision.action.in_(LONG_ACTIONS + SHORT_ACTIONS),
        RecommendationDecision.outcome_status != "PENDING",
    )
    if user_id is not None:
        query = query.filter((RecommendationDecision.user_id == user_id) | (RecommendationDecision.user_id.is_(None)))
    rows = query.order_by(RecommendationDecision.created_at.desc()).limit(PORTFOLIO_BREAKER_LOOKBACK).all()
    wins = sum(1 for row in rows if row.outcome_status == "HIT")
    return {
        "samples": len(rows),
        "win_rate_pct": round(wins / len(rows) * 100, 2) if rows else None,
    }


def _apply_portfolio_circuit_breaker(rows: list[dict], performance: dict) -> bool:
    """Downgrades every BUY_CONTROLLED/SELL_SHORT to its WATCH_* counterpart
    when the AI's recent, portfolio-wide track record (both directions
    combined) falls below a minimum win rate. Returns whether the breaker
    tripped. This never touches WAIT/AVOID rows — it only removes the
    system's permission to size up into a new position while its own recent
    calls have been running cold.
    """
    if performance["samples"] < PORTFOLIO_BREAKER_MIN_SAMPLES:
        return False
    if performance["win_rate_pct"] is None or performance["win_rate_pct"] >= PORTFOLIO_BREAKER_WIN_RATE_PCT:
        return False
    downgrade = {"BUY_CONTROLLED": "WATCH_BUY", "SELL_SHORT": "WATCH_SHORT"}
    for row in rows:
        if row["action"] in downgrade:
            row["action"] = downgrade[row["action"]]
            row["confidence"] = min(row["confidence"], 55)
            row["suggested_size_pct"] = min(row["suggested_size_pct"], 5)
            row["fair_reason"] = (
                f"Rebaixado pelo freio de portfólio: taxa de acerto recente de "
                f"{performance['win_rate_pct']}% em {performance['samples']} recomendações, "
                f"abaixo do mínimo de {PORTFOLIO_BREAKER_WIN_RATE_PCT}%. " + row["fair_reason"]
            )
    return True


def build_decision_health(db: Session, user) -> dict:
    """Operational guardrail based on forward-tested, recorded decisions.

    It deliberately evaluates only completed 5-day outcomes.  Until there is
    enough evidence, the desk may explain and rank setups, but it cannot
    elevate one to a controlled entry.
    """
    user_id = getattr(user, "id", None)
    query = db.query(RecommendationDecision).filter(
        RecommendationDecision.action.in_(LONG_ACTIONS + SHORT_ACTIONS),
        RecommendationDecision.outcome_status != "PENDING",
    )
    if user_id is not None:
        query = query.filter((RecommendationDecision.user_id == user_id) | (RecommendationDecision.user_id.is_(None)))
    rows = query.order_by(RecommendationDecision.created_at.desc()).limit(100).all()
    samples = len(rows)
    wins = sum(row.outcome_status == "HIT" for row in rows)
    win_rate = round(wins / samples * 100, 2) if samples else None
    calibration_error = (
        round(sum(abs(row.confidence / 100 - (1 if row.outcome_status == "HIT" else 0)) for row in rows) / samples, 4)
        if samples
        else None
    )
    if samples < settings.decision_health_min_samples:
        return {
            "operating_mode": "OBSERVATION_ONLY",
            "allowed": False,
            "samples": samples,
            "win_rate_pct": win_rate,
            "calibration_error": calibration_error,
            "reason": f"Amostra insuficiente: {samples}/{settings.decision_health_min_samples} outcomes de 5d.",
        }
    if win_rate is None or win_rate < settings.decision_health_min_win_rate_pct:
        return {
            "operating_mode": "PROTECTED",
            "allowed": False,
            "samples": samples,
            "win_rate_pct": win_rate,
            "calibration_error": calibration_error,
            "reason": f"Acerto recente de {win_rate}% abaixo do mínimo de {settings.decision_health_min_win_rate_pct}%.",
        }
    return {
        "operating_mode": "GUARDED",
        "allowed": True,
        "samples": samples,
        "win_rate_pct": win_rate,
        "calibration_error": calibration_error,
        "reason": "Evidência mínima atingida; risco e qualidade de dados continuam obrigatórios.",
    }


def _apply_decision_health_gate(rows: list[dict], health: dict) -> bool:
    if health["allowed"]:
        return False
    downgrade = {"BUY_CONTROLLED": "WATCH_BUY", "SELL_SHORT": "WATCH_SHORT"}
    for row in rows:
        if row["action"] in downgrade:
            row["action"] = downgrade[row["action"]]
            row["suggested_size_pct"] = 0.0
            row["fair_reason"] = f"{health['reason']} {row['fair_reason']}"
    return True


async def build_decision_desk(db: Session, user, record: bool = False) -> dict:
    evaluate_pending_outcomes(db)
    symbols = _active_symbols(db)
    benchmark = sim.benchmark_context()
    thresholds = effective_thresholds()
    short_thresholds = short_effective_thresholds()
    macro_context = sim.macro_snapshot(benchmark, len(benchmark["history"]) - 1) if benchmark is not None else sim.macro_snapshot(None, 0)
    rows = []
    skipped = []
    for symbol in symbols:
        history = sim._history(symbol)
        if history.empty or len(history) < 120:
            skipped.append(symbol)
            continue
        data = sim._prepared(history)
        rows.append(_recommendation(symbol, data, benchmark, db, getattr(user, "id", None), thresholds, short_thresholds))
    rows.sort(key=lambda row: (row["action"] == "BUY_CONTROLLED", row["confidence"], row["score"]), reverse=True)

    performance = _portfolio_recent_performance(db, getattr(user, "id", None))
    breaker_tripped = _apply_portfolio_circuit_breaker(rows, performance)
    decision_health = build_decision_health(db, user)
    health_gate_tripped = _apply_decision_health_gate(rows, decision_health)
    for row in rows:
        row["decision_card"] = build_decision_card(row)
    await _attach_ai_narratives(rows)

    workspace = get_or_create_workspace(db, user)
    recorded = 0
    if record:
        for row in rows:
            decision = RecommendationDecision(
                user_id=getattr(user, "id", None),
                workspace_id=workspace.id,
                symbol=row["symbol"],
                action=row["action"],
                confidence=row["confidence"],
                score=row["score"],
                price=row["price"],
                suggested_size_pct=row["suggested_size_pct"],
                stop_price=row["stop_price"],
                target_price=row["target_price"],
                thesis=row["thesis"],
                fair_reason=row["fair_reason"],
                invalidation=row["invalidation"],
                evidence_json=_json(row["evidence"]),
                memory_json=_json(row["memory"]),
                horizon=row["prediction"]["horizon"],
                direction=row["prediction"]["direction"],
                probability=row["prediction"]["probability"],
                uncertainty=row["prediction"]["uncertainty"],
                regime=row["prediction"]["regime"],
                model_id=row["prediction"]["model_id"],
                model_version=row["prediction"]["model_version"],
                dataset_version=row["prediction"]["dataset_version"],
                quality_score=row["prediction"]["quality_score"],
                prediction_json=_json(row["prediction"]),
                data_as_of=(
                    datetime.fromisoformat(row["prediction"]["data_as_of"])
                    if row["prediction"].get("data_as_of")
                    else None
                ),
            )
            db.add(decision)
            recorded += 1
        db.commit()

    buy_count = len([row for row in rows if row["action"] == "BUY_CONTROLLED"])
    watch_count = len([row for row in rows if row["action"] == "WATCH_BUY"])
    short_count = len([row for row in rows if row["action"] == "SELL_SHORT"])
    watch_short_count = len([row for row in rows if row["action"] == "WATCH_SHORT"])
    parts = []
    if buy_count or watch_count:
        parts.append(f"{buy_count} compra controlada e {watch_count} ativos em observação de compra")
    if short_count or watch_short_count:
        parts.append(f"{short_count} venda a descoberto e {watch_short_count} ativos em observação de venda")
    headline = (
        ", ".join(parts) + "."
        if parts
        else "Sem compra ou venda confiável agora; preservar caixa é parte da estratégia."
    )
    if breaker_tripped:
        headline = (
            f"Freio de portfólio ativado ({performance['win_rate_pct']}% de acerto nas últimas "
            f"{performance['samples']} recomendações) — posições rebaixadas para observação. " + headline
        )
    return {
        "generated_at": datetime.now(timezone.utc),
        "headline": headline,
        "benchmark": sim.BENCHMARK_SYMBOL,
        "recorded": recorded,
        "skipped": skipped,
        "recommendations": rows,
        "circuit_breaker": {"tripped": breaker_tripped, **performance},
        "decision_health": {"tripped": health_gate_tripped, **decision_health},
        "calibration_source": thresholds["source"],
        "short_calibration_source": short_thresholds["source"],
        "macro_context": macro_context,
    }


CONFIDENCE_BUCKETS = [(0, 39), (40, 59), (60, 69), (70, 79), (80, 100)]


def _confidence_bucket_label(confidence: int) -> str:
    for low, high in CONFIDENCE_BUCKETS:
        if low <= confidence <= high:
            return f"{low}-{high}"
    return f"{CONFIDENCE_BUCKETS[-1][0]}-{CONFIDENCE_BUCKETS[-1][1]}"


def build_market_divergence(db: Session, user) -> dict:
    """Compares the AI's own day-over-day directional lean (how much more
    bullish-weighted vs bearish-weighted its recommendations were) against
    what the benchmark actually did — this is the exact situation a person
    can spot by eye ("today the metrics fell but the market rose") turned
    into a standing check. Needs at least 2 distinct calendar days of
    recorded recommendations (see app.scheduler.record_decision_desk_snapshot,
    which now records one automatically every day) to say anything.
    """
    benchmark_history = sim._history(sim.BENCHMARK_SYMBOL)
    if benchmark_history.empty or len(benchmark_history) < 2:
        return {"available": False, "reason": "Sem histórico de benchmark disponível."}
    close = benchmark_history["close"]
    benchmark_by_date = {ts.date(): float(close.iloc[idx]) for idx, ts in enumerate(benchmark_history.index)}

    user_id = getattr(user, "id", None)
    query = db.query(RecommendationDecision).order_by(RecommendationDecision.created_at.asc())
    if user_id is not None:
        query = query.filter((RecommendationDecision.user_id == user_id) | (RecommendationDecision.user_id.is_(None)))
    rows = query.all()
    if not rows:
        return {"available": False, "reason": "Nenhuma recomendação registrada ainda."}

    by_day: dict = {}
    for row in rows:
        by_day.setdefault(row.created_at.date(), []).append(row)
    days = sorted(by_day.keys())
    if len(days) < 2:
        return {
            "available": False,
            "reason": f"Só há recomendações registradas em {len(days)} dia(s) — preciso de pelo menos 2 pra comparar.",
        }

    def _lean(day_rows: list) -> float:
        bullish = sum(row.confidence for row in day_rows if row.action in LONG_ACTIONS)
        bearish = sum(row.confidence for row in day_rows if row.action in SHORT_ACTIONS)
        return bullish - bearish

    today, yesterday = days[-1], days[-2]
    lean_today = _lean(by_day[today])
    lean_yesterday = _lean(by_day[yesterday])
    lean_change = lean_today - lean_yesterday

    price_today = benchmark_by_date.get(today)
    price_yesterday = benchmark_by_date.get(yesterday)
    benchmark_move_pct = (
        round((price_today / price_yesterday - 1) * 100, 2)
        if price_today is not None and price_yesterday is not None and price_yesterday
        else None
    )

    divergent = benchmark_move_pct is not None and (
        (lean_change < 0 and benchmark_move_pct > 0) or (lean_change > 0 and benchmark_move_pct < 0)
    )
    if benchmark_move_pct is None:
        note = f"Sem preço do {sim.BENCHMARK_SYMBOL} para um dos dois dias — comparação incompleta."
    elif divergent and lean_change < 0:
        note = (
            f"A convicção líquida da IA (compra menos venda) caiu de {lean_yesterday} para {lean_today} "
            f"enquanto o {sim.BENCHMARK_SYMBOL} subiu {benchmark_move_pct}% — vale checar o contexto macro "
            "(DXY, petróleo, VIX) antes de confiar cegamente no placar de hoje."
        )
    elif divergent:
        note = (
            f"A convicção líquida da IA subiu de {lean_yesterday} para {lean_today} enquanto o "
            f"{sim.BENCHMARK_SYMBOL} caiu {benchmark_move_pct}% — pode ser a IA antecipando uma reversão, ou "
            "só estar desalinhada; vale olhar as recomendações individuais."
        )
    else:
        note = "Sem divergência relevante entre a leitura da IA e o movimento do mercado nesse período."

    return {
        "available": True,
        "today": str(today),
        "yesterday": str(yesterday),
        "ai_lean_today": lean_today,
        "ai_lean_yesterday": lean_yesterday,
        "ai_lean_change": lean_change,
        "benchmark_symbol": sim.BENCHMARK_SYMBOL,
        "benchmark_move_pct": benchmark_move_pct,
        "divergent": divergent,
        "note": note,
    }


def build_reliability_scoreboard(db: Session, user, trend_chunk_size: int = 10) -> dict:
    """The AI's own scoreboard, built only from recommendations it already
    logged and later checked against real 5-day outcomes.

    Two questions this answers that a single "confidence: 82%" number can't:
    (1) calibration — when it says 80% confidence, does it actually win ~80%
    of the time, or is that number decorative; (2) trend — is it getting
    better or worse as more recommendations get checked.
    """
    user_id = getattr(user, "id", None)
    query = db.query(RecommendationDecision).filter(
        RecommendationDecision.action.in_(["BUY_CONTROLLED", "WATCH_BUY"]),
        RecommendationDecision.outcome_status != "PENDING",
    )
    if user_id is not None:
        query = query.filter((RecommendationDecision.user_id == user_id) | (RecommendationDecision.user_id.is_(None)))
    rows = query.order_by(RecommendationDecision.created_at.asc()).all()

    total = len(rows)
    wins = sum(1 for row in rows if row.outcome_status == "HIT")
    overall_win_rate = round(wins / total * 100, 2) if total else 0.0

    bucket_totals = {f"{low}-{high}": {"samples": 0, "wins": 0} for low, high in CONFIDENCE_BUCKETS}
    for row in rows:
        bucket = bucket_totals[_confidence_bucket_label(row.confidence)]
        bucket["samples"] += 1
        if row.outcome_status == "HIT":
            bucket["wins"] += 1

    calibration = []
    for low, high in CONFIDENCE_BUCKETS:
        label = f"{low}-{high}"
        bucket = bucket_totals[label]
        win_rate = round(bucket["wins"] / bucket["samples"] * 100, 2) if bucket["samples"] else None
        calibration.append(
            {
                "label": label,
                "samples": bucket["samples"],
                "actual_win_rate_pct": win_rate,
                "midpoint_confidence": (low + high) / 2,
            }
        )

    trend = []
    for i in range(0, total, trend_chunk_size):
        chunk = rows[i : i + trend_chunk_size]
        chunk_wins = sum(1 for row in chunk if row.outcome_status == "HIT")
        trend.append(
            {
                "period_label": f"#{i + 1}-{i + len(chunk)}",
                "samples": len(chunk),
                "win_rate_pct": round(chunk_wins / len(chunk) * 100, 2),
                "ends_at": chunk[-1].created_at,
            }
        )

    return {
        "total_samples": total,
        "overall_win_rate_pct": overall_win_rate,
        "calibration": calibration,
        "trend": trend,
    }


def latest_decisions(db: Session, user, limit: int = 50) -> list[dict]:
    query = db.query(RecommendationDecision)
    user_id = getattr(user, "id", None)
    if user_id is not None:
        query = query.filter((RecommendationDecision.user_id == user_id) | (RecommendationDecision.user_id.is_(None)))
    rows = query.order_by(RecommendationDecision.created_at.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "symbol": row.symbol,
            "action": row.action,
            "confidence": row.confidence,
            "score": row.score,
            "price": row.price,
            "suggested_size_pct": row.suggested_size_pct,
            "stop_price": row.stop_price,
            "target_price": row.target_price,
            "thesis": row.thesis,
            "fair_reason": row.fair_reason,
            "invalidation": row.invalidation,
            "evidence": _loads(row.evidence_json, []),
            "memory": _loads(row.memory_json, {}),
            "outcome_status": row.outcome_status,
            "outcome_return_1d_pct": row.outcome_return_1d_pct,
            "outcome_return_5d_pct": row.outcome_return_5d_pct,
            "outcome_return_20d_pct": row.outcome_return_20d_pct,
            "regime": row.regime,
            "model_id": row.model_id,
            "model_version": row.model_version,
            "prediction": _loads(row.prediction_json, {}),
            "created_at": row.created_at,
        }
        for row in rows
    ]
