from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from app import indicators
from app.db import SessionLocal
from app.market_data import service as market_data_service
from app.models import WatchlistItem

DEFAULT_SYMBOLS = [
    # Mega-cap tech (correlacionado, o nucleo original)
    "AAPL",
    "MSFT",
    "NVDA",
    "AMD",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "AVGO",
    "NFLX",
    "COST",
    "ADBE",
    "CSCO",
    "QCOM",
    "PLTR",
    "SNAP",
    # Saude/biotech (Nasdaq-100, ciclo proprio, pouco correlacionado com tech)
    "REGN",
    "VRTX",
    "GILD",
    "AMGN",
    # Consumo defensivo, industrial, pagamentos, midia (diversifica regime de mercado)
    "MDLZ",
    "HON",
    "PYPL",
    "CMCSA",
]
# Was hardcoded to "2y" at every call site (here, VIX fetch, macro fetch) — silently
# capped every walk-forward/research experiment to the same ~2-year window regardless
# of how much history yfinance actually has for a symbol. Configurable now so research
# scripts can test whether more history changes the "no edge found" conclusion in
# docs/data_phase_findings.md before spending on paid alternative data.
MARKET_HISTORY_PERIOD = os.getenv("MARKET_HISTORY_PERIOD", "2y")
DATA_DIR = Path(os.getenv("PAPER_SIM_DATA_DIR", "data"))
STATE_PATH = DATA_DIR / "paper_simulator_state.json"
EVENTS_PATH = DATA_DIR / "paper_simulator_events.jsonl"
DEEP_REPLAY_PATH = DATA_DIR / "paper_simulator_deep_replay.json"
INITIAL_CAPITAL = float(os.getenv("PAPER_SIM_INITIAL_CAPITAL", "10000"))
RELIABLE_PRECISION_PCT = float(os.getenv("PAPER_SIM_RELIABLE_PRECISION_PCT", "58"))
AI_FIRST_MODE = os.getenv("PAPER_SIM_AI_FIRST_MODE", "false").lower() == "true"
AI_FIRST_MIN_PRECISION_PCT = float(os.getenv("PAPER_SIM_AI_FIRST_MIN_PRECISION_PCT", "50"))
REPLAY_DAYS = int(os.getenv("PAPER_SIM_REPLAY_DAYS", "180"))
MAX_POSITION_PCT = float(os.getenv("PAPER_SIM_MAX_POSITION_PCT", "0.25"))
REPLAY_CALIBRATION_INTERVAL_DAYS = int(os.getenv("PAPER_SIM_REPLAY_CALIBRATION_INTERVAL_DAYS", "10"))
FORCE_REPLAY_TRADES = os.getenv("PAPER_SIM_FORCE_TRADES", "false").lower() == "true"
BENCHMARK_SYMBOL = os.getenv("PAPER_SIM_BENCHMARK", "QQQ")
COST_BPS = float(os.getenv("PAPER_SIM_COST_BPS", "2"))
SLIPPAGE_BPS = float(os.getenv("PAPER_SIM_SLIPPAGE_BPS", "5"))
MAX_OPEN_POSITIONS = int(os.getenv("PAPER_SIM_MAX_OPEN_POSITIONS", "4"))
STOP_ATR_MULTIPLIER = float(os.getenv("PAPER_SIM_STOP_ATR_MULTIPLIER", "1.25"))
TARGET_ATR_MULTIPLIER = float(os.getenv("PAPER_SIM_TARGET_ATR_MULTIPLIER", "2.2"))
PARTIAL_SELL_FRACTION = float(os.getenv("PAPER_SIM_PARTIAL_SELL_FRACTION", "0.5"))


@dataclass
class FilterParams:
    rsi_low: int
    rsi_high: int
    min_volume_ratio: float
    max_atr_pct: float
    max_annualized_volatility: float
    min_score: int = 70


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_state() -> dict:
    if not STATE_PATH.exists():
        return {"cash": INITIAL_CAPITAL, "initial_capital": INITIAL_CAPITAL, "positions": {}, "closed_trades": []}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def _save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _log(event: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"at": _now_iso(), **event}
    with EVENTS_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _save_deep_replay(result: dict) -> None:
    DEEP_REPLAY_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEEP_REPLAY_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def _symbols() -> list[str]:
    override = os.getenv("PAPER_SIM_SYMBOLS", "").strip()
    if override:
        return sorted({symbol.strip().upper() for symbol in override.split(",") if symbol.strip()})

    db = SessionLocal()
    try:
        items = db.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).all()
        symbols = [item.symbol.upper() for item in items]
    finally:
        db.close()
    return sorted(set(symbols or DEFAULT_SYMBOLS))


def _history(symbol: str, period: str = MARKET_HISTORY_PERIOD) -> pd.DataFrame:
    history = market_data_service.get_bars(symbol, period=period, interval="1d")
    if history.empty:
        return history
    return history.dropna(subset=["open", "high", "low", "close", "volume"])


def _prepared(history: pd.DataFrame) -> dict:
    close = history["close"]
    return {
        "history": history,
        "sma20": indicators.sma(close, 20),
        "sma50": indicators.sma(close, 50),
        "sma200": indicators.sma(close, 200),
        "ema9": indicators.ema(close, 9),
        "ema21": indicators.ema(close, 21),
        "rsi": indicators.rsi(close),
        "macd": indicators.macd(close),
        "volume_ratio": indicators.volume_ratio(history["volume"]),
        "atr": indicators.atr(history["high"], history["low"], close),
        "annualized_volatility": indicators.annualized_volatility(close),
        "recent_high20": close.shift(1).rolling(window=20, min_periods=20).max(),
        "recent_low20": close.shift(1).rolling(window=20, min_periods=20).min(),
        "return20": close.pct_change(20) * 100,
    }


def _buy_base(data: dict, i: int) -> bool:
    return (
        data["ema9"].iloc[i] > data["ema21"].iloc[i]
        and data["macd"]["macd"].iloc[i] > data["macd"]["signal"].iloc[i]
    )


def _sell_base(data: dict, i: int) -> bool:
    return (
        data["ema9"].iloc[i] < data["ema21"].iloc[i]
        and data["macd"]["macd"].iloc[i] < data["macd"]["signal"].iloc[i]
    )


def _indicators_ready(data: dict, i: int) -> bool:
    values = [
        data["sma20"].iloc[i],
        data["sma50"].iloc[i],
        data["ema9"].iloc[i],
        data["ema21"].iloc[i],
        data["rsi"].iloc[i],
        data["macd"]["macd"].iloc[i],
        data["macd"]["signal"].iloc[i],
        data["volume_ratio"].iloc[i],
        data["atr"].iloc[i],
        data["annualized_volatility"].iloc[i],
        data["recent_high20"].iloc[i],
        data["return20"].iloc[i],
    ]
    return not any(pd.isna(value) for value in values)


VIX_SYMBOL = os.getenv("PAPER_SIM_VIX_SYMBOL", "^VIX")
VIX_RISK_OFF_LEVEL = float(os.getenv("PAPER_SIM_VIX_RISK_OFF_LEVEL", "28"))
VIX_CAUTION_LEVEL = float(os.getenv("PAPER_SIM_VIX_CAUTION_LEVEL", "22"))
VIX_CALM_LEVEL = float(os.getenv("PAPER_SIM_VIX_CALM_LEVEL", "18"))


def _fetch_vix_series(reference_index: pd.Index) -> pd.Series | None:
    """Aligns real VIX closes onto the benchmark's own trading-day index.

    Best-effort: any fetch/alignment failure returns None, and callers treat
    a missing VIX series exactly like "no data" — the rest of the market
    regime score still works, this only adds a real tail-risk signal on top.
    """
    try:
        vix_history = market_data_service.get_bars(VIX_SYMBOL, period=MARKET_HISTORY_PERIOD, interval="1d")
    except Exception:
        return None
    if vix_history.empty or "close" not in vix_history.columns:
        return None
    try:
        return vix_history["close"].dropna().reindex(reference_index, method="ffill")
    except Exception:
        return None


DXY_SYMBOL = os.getenv("PAPER_SIM_DXY_SYMBOL", "DX-Y.NYB")
OIL_SYMBOL = os.getenv("PAPER_SIM_OIL_SYMBOL", "CL=F")


def _fetch_macro_series(symbol: str, reference_index: pd.Index) -> pd.Series | None:
    """Same best-effort fetch+align pattern as _fetch_vix_series, reused for
    any macro instrument we just want aligned onto the benchmark's trading
    days (DXY, oil) — returns None on any failure, never raises."""
    try:
        history = market_data_service.get_bars(symbol, period=MARKET_HISTORY_PERIOD, interval="1d")
    except Exception:
        return None
    if history.empty or "close" not in history.columns:
        return None
    try:
        return history["close"].dropna().reindex(reference_index, method="ffill")
    except Exception:
        return None


def benchmark_context() -> dict | None:
    """Single entry point for building the benchmark used by _market_regime —
    QQQ's own prepared indicators plus real VIX/DXY/oil series aligned to it.

    VIX feeds the risk_off gate directly (see _market_regime). DXY and oil
    are informational only — exposed via macro_snapshot() for display/LLM
    context, not folded into the opportunity score, so the already-tuned
    scoring thresholds don't shift underneath existing calibration.
    """
    benchmark_history = _history(BENCHMARK_SYMBOL)
    if benchmark_history.empty or len(benchmark_history) < 120:
        return None
    benchmark = _prepared(benchmark_history)
    benchmark["vix"] = _fetch_vix_series(benchmark_history.index)
    benchmark["dxy"] = _fetch_macro_series(DXY_SYMBOL, benchmark_history.index)
    benchmark["oil"] = _fetch_macro_series(OIL_SYMBOL, benchmark_history.index)
    return benchmark


def _vix_level_at(benchmark: dict, i: int) -> float | None:
    vix_series = benchmark.get("vix")
    if vix_series is None or i >= len(vix_series):
        return None
    raw = vix_series.iloc[i]
    return None if pd.isna(raw) else float(raw)


def macro_snapshot(benchmark: dict | None, i: int) -> dict:
    """Informational macro read (DXY, oil) at bar i: level + 20-trading-day
    change. Purely for a human (or the LLM narrator) to see broader market
    positioning alongside a recommendation — never changes the score or the
    action the rule engine picks.
    """
    empty = {"dxy": None, "dxy_change_20d_pct": None, "oil": None, "oil_change_20d_pct": None}
    if benchmark is None:
        return empty

    def _level_and_change(series: pd.Series | None) -> tuple[float | None, float | None]:
        if series is None or i >= len(series):
            return None, None
        level = series.iloc[i]
        if pd.isna(level):
            return None, None
        past = series.iloc[max(0, i - 20)]
        change = ((float(level) / float(past) - 1) * 100) if not pd.isna(past) and past else None
        return round(float(level), 2), round(change, 2) if change is not None else None

    dxy_level, dxy_change = _level_and_change(benchmark.get("dxy"))
    oil_level, oil_change = _level_and_change(benchmark.get("oil"))
    return {
        "dxy": dxy_level,
        "dxy_change_20d_pct": dxy_change,
        "oil": oil_level,
        "oil_change_20d_pct": oil_change,
    }


def _market_regime(benchmark: dict | None, i: int) -> dict:
    if benchmark is None or i >= len(benchmark["history"]) or not _indicators_ready(benchmark, i):
        return {"score": 10, "state": "unknown", "risk_multiplier": 0.7, "vix": None}
    close = float(benchmark["history"]["close"].iloc[i])
    sma50 = float(benchmark["sma50"].iloc[i])
    sma200 = benchmark["sma200"].iloc[i]
    ema_ok = float(benchmark["ema9"].iloc[i]) > float(benchmark["ema21"].iloc[i])
    vol = float(benchmark["annualized_volatility"].iloc[i])
    score = 0
    if close > sma50:
        score += 8
    if not pd.isna(sma200) and close > float(sma200):
        score += 7
    if ema_ok:
        score += 5
    if vol <= 35:
        score += 5
    elif vol <= 55:
        score += 2

    vix_level = _vix_level_at(benchmark, i)
    vix_risk_off = vix_level is not None and vix_level >= VIX_RISK_OFF_LEVEL
    if vix_level is not None:
        if vix_level < VIX_CALM_LEVEL:
            score += 3
        elif vix_level < VIX_CAUTION_LEVEL:
            pass
        elif vix_level < VIX_RISK_OFF_LEVEL:
            score -= 4
        else:
            score -= 10

    state = "bullish" if score >= 18 else "neutral" if score >= 11 else "risk_off"
    if vix_risk_off:
        state = "risk_off"
    risk_multiplier = 1.0 if state == "bullish" else 0.65 if state == "neutral" else 0.35
    return {"score": score, "state": state, "risk_multiplier": risk_multiplier, "vix": vix_level}


def _opportunity_score(data: dict, i: int, benchmark: dict | None = None) -> tuple[int, dict]:
    if not _indicators_ready(data, i):
        return 0, {"reason": "indicators_not_ready"}
    price = float(data["history"]["close"].iloc[i])
    atr = float(data["atr"].iloc[i])
    atr_pct = atr / price * 100
    trend = 0
    if price > float(data["sma20"].iloc[i]):
        trend += 6
    if price > float(data["sma50"].iloc[i]):
        trend += 8
    if float(data["ema9"].iloc[i]) > float(data["ema21"].iloc[i]):
        trend += 6
    if price > float(data["recent_high20"].iloc[i]):
        trend += 5

    volume = min(15, max(0, int((float(data["volume_ratio"].iloc[i]) - 0.8) * 18)))
    relative = 10
    if benchmark is not None and i < len(benchmark["history"]) and not pd.isna(benchmark["return20"].iloc[i]):
        relative_return = float(data["return20"].iloc[i]) - float(benchmark["return20"].iloc[i])
        relative = min(20, max(0, int(10 + relative_return * 1.4)))

    risk_reward = 20 if 0.8 <= atr_pct <= 4 else 12 if atr_pct <= 6 else 5
    if float(data["rsi"].iloc[i]) > 72:
        risk_reward -= 6
    if float(data["rsi"].iloc[i]) < 42:
        risk_reward -= 4
    risk_reward = max(0, risk_reward)

    market = _market_regime(benchmark, i)
    score = min(100, trend + volume + relative + risk_reward + int(market["score"]))
    details = {
        "score": score,
        "trend": trend,
        "volume": volume,
        "relative_strength": relative,
        "risk_reward": risk_reward,
        "market": market,
        "atr_pct": round(atr_pct, 2),
    }
    return score, details


FEATURE_NAMES = [
    "score",
    "trend",
    "volume_component",
    "relative_strength",
    "risk_reward",
    "rsi",
    "volume_ratio",
    "atr_pct",
    "annualized_volatility",
    "market_score",
    "vix",
]

_VIX_NEUTRAL_FALLBACK = 20.0


def feature_vector(data: dict, i: int, benchmark: dict | None = None) -> list[float] | None:
    """The single source of truth for what the probability model sees.

    Shared by scripts/train_probability_model.py (offline training) and
    app.decision_engine (live inference) so the two can never drift apart —
    a mismatch there would silently corrupt every prediction.
    """
    if not _indicators_ready(data, i):
        return None
    score, details = _opportunity_score(data, i, benchmark)
    vix = details["market"].get("vix")
    return [
        float(score),
        float(details["trend"]),
        float(details["volume"]),
        float(details["relative_strength"]),
        float(details["risk_reward"]),
        float(data["rsi"].iloc[i]),
        float(data["volume_ratio"].iloc[i]),
        float(details["atr_pct"]),
        float(data["annualized_volatility"].iloc[i]),
        float(details["market"]["score"]),
        float(vix) if vix is not None else _VIX_NEUTRAL_FALLBACK,
    ]


def _passes_filter(data: dict, i: int, params: FilterParams, benchmark: dict | None = None) -> bool:
    price = float(data["history"]["close"].iloc[i])
    atr_pct = float(data["atr"].iloc[i] / price * 100)
    score, details = _opportunity_score(data, i, benchmark)
    return (
        _buy_base(data, i)
        and params.rsi_low <= float(data["rsi"].iloc[i]) <= params.rsi_high
        and float(data["volume_ratio"].iloc[i]) >= params.min_volume_ratio
        and atr_pct <= params.max_atr_pct
        and float(data["annualized_volatility"].iloc[i]) <= params.max_annualized_volatility
        and details["market"]["state"] != "risk_off"
        and score >= params.min_score
    )


def _candidate_filters() -> list[FilterParams]:
    filters = []
    for rsi_low in [45, 48, 50, 52]:
        for rsi_high in [58, 62, 65, 68]:
            for min_volume_ratio in [0.9, 1.0, 1.1, 1.25, 1.4]:
                for max_atr_pct in [2.5, 3, 4, 5, 6]:
                    for max_annualized_volatility in [35, 45, 60, 75, 90]:
                        for min_score in [62, 68, 74, 80]:
                            filters.append(
                                FilterParams(
                                    rsi_low,
                                    rsi_high,
                                    min_volume_ratio,
                                    max_atr_pct,
                                    max_annualized_volatility,
                                    min_score,
                                )
                            )
    return filters


def _candidate_replay_filters() -> list[FilterParams]:
    filters = []
    for rsi_low in [45, 50]:
        for rsi_high in [62, 68]:
            for min_volume_ratio in [0.9, 1.1]:
                for max_atr_pct in [4, 6]:
                    for max_annualized_volatility in [60, 90]:
                        for min_score in [62, 70, 78]:
                            filters.append(
                                FilterParams(
                                    rsi_low,
                                    rsi_high,
                                    min_volume_ratio,
                                    max_atr_pct,
                                    max_annualized_volatility,
                                    min_score,
                                )
                            )
    return filters


def calibrate(symbols: list[str]) -> tuple[FilterParams | None, dict, dict[str, dict]]:
    prepared = {}
    rows = []
    benchmark = benchmark_context()
    for symbol in symbols:
        history = _history(symbol)
        if history.empty or len(history) < 90:
            _log({"type": "symbol_skipped", "symbol": symbol, "reason": "Sem historico suficiente no yfinance."})
            continue
        data = _prepared(history)
        prepared[symbol] = data
        close = history["close"]
        for i in range(60, len(history) - 5):
            if not _indicators_ready(data, i):
                continue
            price = float(close.iloc[i])
            forward_return = (float(close.iloc[i + 5]) / price - 1) * 100
            rows.append((symbol, i, forward_return))

    best = None
    for params in _candidate_filters():
        chosen = []
        for symbol, i, forward_return in rows:
            if _passes_filter(prepared[symbol], i, params, benchmark):
                chosen.append(forward_return)
        if len(chosen) < 20:
            continue
        true_positive = sum(1 for value in chosen if value > 0.5)
        precision = true_positive / len(chosen) * 100
        average_return = sum(chosen) / len(chosen)
        score = precision + max(-10, min(10, average_return * 4)) + min(8, len(chosen) / 20)
        result = {
            "params": asdict(params),
            "signals": len(chosen),
            "precision_pct": round(precision, 2),
            "false_positive": len(chosen) - true_positive,
            "avg_5d_return_pct": round(average_return, 2),
            "score": round(score, 2),
        }
        if best is None or result["score"] > best["result"]["score"]:
            best = {"params": params, "result": result}

    if best is None:
        return None, {"status": "no_reliable_filter", "reason": "Sem amostra minima de 20 sinais."}, prepared
    reliable = best["result"]["precision_pct"] >= RELIABLE_PRECISION_PCT and best["result"]["avg_5d_return_pct"] > 0
    ai_first = (
        AI_FIRST_MODE
        and best["result"]["precision_pct"] >= AI_FIRST_MIN_PRECISION_PCT
        and best["result"]["avg_5d_return_pct"] > 0
    )
    if reliable:
        best["result"]["status"] = "reliable"
    elif ai_first:
        best["result"]["status"] = "ai_first_validation"
        best["result"]["reason"] = (
            f"Modo AI_FIRST: seguindo a melhor leitura da IA para validar threshold; "
            f"alvo confiavel {RELIABLE_PRECISION_PCT}% ainda nao atingido."
        )
    else:
        best["result"]["status"] = "not_reliable"
    return (best["params"] if reliable or ai_first else None), best["result"], prepared


def _is_replay_reliable(calibration: dict) -> bool:
    return (
        calibration.get("signals", 0) >= 12
        and calibration.get("precision_pct", 0) >= max(52.0, RELIABLE_PRECISION_PCT - 6)
        and calibration.get("avg_5d_return_pct", 0) > 0
    )


def _is_replay_ai_first(calibration: dict) -> bool:
    return (
        AI_FIRST_MODE
        and calibration.get("signals", 0) >= 12
        and calibration.get("precision_pct", 0) >= AI_FIRST_MIN_PRECISION_PCT
        and calibration.get("avg_5d_return_pct", 0) > 0
    )


def _calibrate_until(
    prepared: dict[str, dict], end_index_by_symbol: dict[str, int], benchmark: dict | None = None
) -> tuple[FilterParams | None, dict]:
    rows = []
    for symbol, data in prepared.items():
        history = data["history"]
        end = min(end_index_by_symbol.get(symbol, 0), len(history) - 6)
        for i in range(60, end):
            if not _indicators_ready(data, i):
                continue
            price = float(history["close"].iloc[i])
            forward_return = (float(history["close"].iloc[i + 5]) / price - 1) * 100
            score, details = _opportunity_score(data, i, benchmark)
            rows.append(
                {
                    "symbol": symbol,
                    "i": i,
                    "forward_return": forward_return,
                    "buy_base": _buy_base(data, i),
                    "rsi": float(data["rsi"].iloc[i]),
                    "volume_ratio": float(data["volume_ratio"].iloc[i]),
                    "atr_pct": float(data["atr"].iloc[i] / price * 100),
                    "annualized_volatility": float(data["annualized_volatility"].iloc[i]),
                    "score": score,
                    "market_state": details["market"]["state"],
                }
            )

    best = None
    for params in _candidate_replay_filters():
        chosen = []
        for row in rows:
            if (
                row["buy_base"]
                and params.rsi_low <= row["rsi"] <= params.rsi_high
                and row["volume_ratio"] >= params.min_volume_ratio
                and row["atr_pct"] <= params.max_atr_pct
                and row["annualized_volatility"] <= params.max_annualized_volatility
                and row["market_state"] != "risk_off"
                and row["score"] >= params.min_score
            ):
                chosen.append(row["forward_return"])
        if len(chosen) < 12:
            continue
        true_positive = sum(1 for value in chosen if value > 0.5)
        precision = true_positive / len(chosen) * 100
        average_return = sum(chosen) / len(chosen)
        score = precision + max(-10, min(10, average_return * 4)) + min(8, len(chosen) / 20)
        result = {
            "params": asdict(params),
            "signals": len(chosen),
            "precision_pct": round(precision, 2),
            "false_positive": len(chosen) - true_positive,
            "avg_5d_return_pct": round(average_return, 2),
            "score": round(score, 2),
        }
        if best is None or result["score"] > best["result"]["score"]:
            best = {"params": params, "result": result}

    if best is None:
        return None, {"status": "no_reliable_filter", "reason": "Sem amostra minima de 12 sinais no replay."}
    reliable = _is_replay_reliable(best["result"])
    ai_first = _is_replay_ai_first(best["result"])
    if reliable:
        best["result"]["status"] = "reliable"
    elif ai_first:
        best["result"]["status"] = "ai_first_validation"
        best["result"]["reason"] = (
            f"Modo AI_FIRST: seguindo a melhor leitura da IA para validar threshold; "
            f"alvo confiavel {RELIABLE_PRECISION_PCT}% ainda nao atingido."
        )
    else:
        best["result"]["status"] = "not_reliable"
    return (best["params"] if reliable or ai_first else None), best["result"]


def risk_adjusted_metrics(daily_values: list[dict]) -> dict:
    """Sharpe/Sortino from the day-by-day portfolio value curve.

    Win rate and profit factor say nothing about whether a return was worth
    the ride to get there; these do. Annualized assuming ~252 trading days,
    risk-free rate at 0 (fictitious capital, not a real cash alternative).
    Shared by run_deep_replay and scripts/calibrate_decision_strategy.py so
    both report the same thing the same way.
    """
    if len(daily_values) < 3:
        return {"sharpe_ratio": None, "sortino_ratio": None}
    values = [float(row["value"]) for row in daily_values]
    returns = [values[i] / values[i - 1] - 1 for i in range(1, len(values)) if values[i - 1] > 0]
    if len(returns) < 2:
        return {"sharpe_ratio": None, "sortino_ratio": None}
    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_return = variance**0.5
    downside_variance = sum(min(0.0, r) ** 2 for r in returns) / len(returns)
    downside_std = downside_variance**0.5
    annualization = 252**0.5
    sharpe = round((mean_return / std_return) * annualization, 3) if std_return > 0 else None
    sortino = round((mean_return / downside_std) * annualization, 3) if downside_std > 0 else None
    return {"sharpe_ratio": sharpe, "sortino_ratio": sortino}


def _portfolio_value(state: dict, prepared: dict[str, dict]) -> float:
    value = float(state["cash"])
    for symbol, position in state["positions"].items():
        data = prepared.get(symbol)
        if data is None:
            continue
        price = float(data["history"]["close"].iloc[-1])
        value += float(position["shares"]) * price
    return round(value, 2)


def _portfolio_value_at(state: dict, prepared: dict[str, dict], i: int) -> float:
    value = float(state["cash"])
    for symbol, position in state["positions"].items():
        data = prepared.get(symbol)
        if data is None or i >= len(data["history"]):
            continue
        price = float(data["history"]["close"].iloc[i])
        value += float(position["shares"]) * price
    return round(value, 2)


def _buy_execution(price: float) -> float:
    return price * (1 + SLIPPAGE_BPS / 10000)


def _sell_execution(price: float) -> float:
    return price * (1 - SLIPPAGE_BPS / 10000)


def _fee(notional: float) -> float:
    return notional * COST_BPS / 10000


def evaluate_cycle() -> None:
    symbols = _symbols()
    state = _load_state()
    selected_filter, calibration, prepared = calibrate(symbols)
    benchmark = benchmark_context()

    _log(
        {
            "type": "calibration",
            "symbols": symbols,
            "calibration": calibration,
            "portfolio_value": _portfolio_value(state, prepared),
        }
    )

    # Always manage existing positions, even if the current filter is not reliable.
    for symbol, position in list(state["positions"].items()):
        data = prepared.get(symbol)
        if data is None:
            continue
        i = len(data["history"]) - 1
        price = float(data["history"]["close"].iloc[i])
        shares = int(position["shares"])
        atr = float(data["atr"].iloc[i])
        position["stop"] = round(max(float(position["stop"]), price - atr * STOP_ATR_MULTIPLIER), 2)
        reason = ""
        if price <= float(position["stop"]):
            reason = "stop_hit"
        elif price >= float(position["target"]) and not position.get("partial_taken"):
            sell_shares = max(1, int(shares * PARTIAL_SELL_FRACTION))
            execution_price = _sell_execution(price)
            gross = execution_price * sell_shares
            fee = _fee(gross)
            proceeds = round(gross - fee, 2)
            pnl = round((execution_price - float(position["entry_price"])) * sell_shares - fee, 2)
            state["cash"] = round(float(state["cash"]) + proceeds, 2)
            position["shares"] = shares - sell_shares
            position["partial_taken"] = True
            position["stop"] = round(max(float(position["stop"]), float(position["entry_price"])), 2)
            _log(
                {
                    "type": "partial_sell",
                    "symbol": symbol,
                    "price": round(execution_price, 2),
                    "shares": sell_shares,
                    "pnl": pnl,
                    "reason": "target_hit_partial",
                    "fee": round(fee, 2),
                }
            )
            if int(position["shares"]) > 0:
                continue
            reason = "target_hit"
        elif _indicators_ready(data, i) and _sell_base(data, i):
            reason = "trend_flip"
        if not reason:
            _log(
                {
                    "type": "hold",
                    "symbol": symbol,
                    "price": round(price, 2),
                    "shares": shares,
                    "unrealized_pnl": round((price - float(position["entry_price"])) * shares, 2),
                }
            )
            continue
        execution_price = _sell_execution(price)
        gross = execution_price * shares
        fee = _fee(gross)
        proceeds = round(gross - fee, 2)
        pnl = round((execution_price - float(position["entry_price"])) * shares - fee, 2)
        state["cash"] = round(float(state["cash"]) + proceeds, 2)
        state["closed_trades"].append({**position, "exit_price": round(execution_price, 2), "exit_reason": reason, "pnl": pnl})
        del state["positions"][symbol]
        _log({"type": "sell", "symbol": symbol, "price": round(execution_price, 2), "shares": shares, "pnl": pnl, "reason": reason, "fee": round(fee, 2)})

    if selected_filter is None:
        _log({"type": "decision", "decision": "NO_TRADE", "reason": "Filtro historico ainda nao confiavel."})
        _save_state(state)
        return

    opened_trade = False
    for symbol, data in prepared.items():
        if symbol in state["positions"]:
            continue
        i = len(data["history"]) - 1
        if not _indicators_ready(data, i) or not _passes_filter(data, i, selected_filter, benchmark):
            continue
        price = float(data["history"]["close"].iloc[i])
        cash = float(state["cash"])
        budget = min(cash, float(state.get("initial_capital", INITIAL_CAPITAL)) * MAX_POSITION_PCT)
        execution_price = _buy_execution(price)
        shares = int(budget // (execution_price * (1 + COST_BPS / 10000)))
        if shares <= 0:
            _log({"type": "decision", "decision": "SKIP", "symbol": symbol, "reason": "Capital insuficiente para 1 acao inteira."})
            continue
        atr = float(data["atr"].iloc[i])
        stop = round(execution_price - atr * STOP_ATR_MULTIPLIER, 2)
        target = round(execution_price + atr * TARGET_ATR_MULTIPLIER, 2)
        gross = shares * execution_price
        fee = _fee(gross)
        cost = round(gross + fee, 2)
        state["cash"] = round(cash - cost, 2)
        score, score_details = _opportunity_score(data, i, benchmark)
        state["positions"][symbol] = {
            "symbol": symbol,
            "entry_at": _now_iso(),
            "entry_price": round(execution_price, 2),
            "shares": shares,
            "stop": stop,
            "target": target,
            "filter": asdict(selected_filter),
            "score": score,
            "score_details": score_details,
            "buy_fee": round(fee, 2),
        }
        _log(
            {
                "type": "buy",
                "symbol": symbol,
                "price": round(execution_price, 2),
                "shares": shares,
                "cost": cost,
                "stop": stop,
                "target": target,
                "score": score,
                "fee": round(fee, 2),
                "reason": "Filtro historico confiavel + sinal atual confirmado.",
            }
        )
        opened_trade = True
        break

    if not opened_trade:
        _log({"type": "decision", "decision": "NO_TRADE", "reason": "Filtro confiavel, mas nenhum ativo confirmou sinal atual."})

    _save_state(state)


def run_deep_replay(initial_capital: float | None = None, replay_days: int | None = None) -> dict:
    capital = float(initial_capital or INITIAL_CAPITAL)
    symbols = _symbols()
    prepared = {}
    skipped = []
    benchmark = benchmark_context()
    for symbol in symbols:
        history = _history(symbol)
        if history.empty or len(history) < 120:
            skipped.append(symbol)
            continue
        prepared[symbol] = _prepared(history)

    if not prepared:
        result = {"status": "no_data", "symbols": symbols, "skipped": skipped}
        _save_deep_replay(result)
        return result

    max_len = min(len(data["history"]) for data in prepared.values())
    start = max(65, max_len - int(replay_days or REPLAY_DAYS))
    state = {"cash": capital, "initial_capital": capital, "positions": {}, "closed_trades": []}
    events = []
    daily_values = []
    last_calibration = {}
    selected_filter = None

    for i in range(start, max_len):
        if i == start or (i - start) % REPLAY_CALIBRATION_INTERVAL_DAYS == 0:
            selected_filter, calibration = _calibrate_until(prepared, {symbol: i for symbol in prepared}, benchmark)
            if selected_filter is None and FORCE_REPLAY_TRADES:
                selected_filter = FilterParams(35, 78, 0.5, 12, 180)
                calibration = {
                    **calibration,
                    "status": "forced_validation",
                    "reason": "Modo de ensaio: força operações para validar compra, venda e falso positivo.",
                }
            last_calibration = calibration
        day = str(next(iter(prepared.values()))["history"].index[i].date())

        for symbol, position in list(state["positions"].items()):
            data = prepared[symbol]
            price = float(data["history"]["close"].iloc[i])
            shares = int(position["shares"])
            atr = float(data["atr"].iloc[i])
            position["stop"] = round(max(float(position["stop"]), price - atr * STOP_ATR_MULTIPLIER), 2)
            reason = ""
            if price <= float(position["stop"]):
                reason = "stop_hit"
            elif price >= float(position["target"]) and not position.get("partial_taken"):
                sell_shares = max(1, int(shares * PARTIAL_SELL_FRACTION))
                execution_price = _sell_execution(price)
                gross = execution_price * sell_shares
                fee = _fee(gross)
                proceeds = round(gross - fee, 2)
                pnl = round((execution_price - float(position["entry_price"])) * sell_shares - fee, 2)
                state["cash"] = round(float(state["cash"]) + proceeds, 2)
                position["shares"] = shares - sell_shares
                position["partial_taken"] = True
                position["stop"] = round(max(float(position["stop"]), float(position["entry_price"])), 2)
                events.append(
                    {
                        "day": day,
                        "type": "partial_sell",
                        "symbol": symbol,
                        "price": round(execution_price, 2),
                        "shares": sell_shares,
                        "pnl": pnl,
                        "fee": round(fee, 2),
                        "reason": "target_hit_partial",
                    }
                )
                if int(position["shares"]) > 0:
                    continue
                reason = "target_hit"
            elif _indicators_ready(data, i) and _sell_base(data, i):
                reason = "trend_flip"
            if not reason:
                continue
            execution_price = _sell_execution(price)
            gross = execution_price * shares
            fee = _fee(gross)
            proceeds = round(gross - fee, 2)
            pnl = round((execution_price - float(position["entry_price"])) * shares - fee, 2)
            state["cash"] = round(float(state["cash"]) + proceeds, 2)
            closed = {**position, "exit_at": day, "exit_price": round(execution_price, 2), "exit_reason": reason, "pnl": pnl}
            state["closed_trades"].append(closed)
            del state["positions"][symbol]
            events.append({"day": day, "type": "sell", "symbol": symbol, "price": round(execution_price, 2), "shares": shares, "pnl": pnl, "reason": reason, "fee": round(fee, 2)})

        if selected_filter is not None:
            ranked = []
            for symbol, data in prepared.items():
                if symbol in state["positions"] or not _indicators_ready(data, i):
                    continue
                if _passes_filter(data, i, selected_filter, benchmark):
                    score, score_details = _opportunity_score(data, i, benchmark)
                    ranked.append((score, float(data["volume_ratio"].iloc[i]), symbol, data, score_details))
            ranked.sort(reverse=True)
            for score, _, symbol, data, score_details in ranked:
                price = float(data["history"]["close"].iloc[i])
                cash = float(state["cash"])
                market = _market_regime(benchmark, i)
                budget = min(cash, capital * MAX_POSITION_PCT * float(market["risk_multiplier"]))
                execution_price = _buy_execution(price)
                shares = int(budget // (execution_price * (1 + COST_BPS / 10000)))
                if shares <= 0:
                    continue
                atr = float(data["atr"].iloc[i])
                gross = shares * execution_price
                fee = _fee(gross)
                cost = round(gross + fee, 2)
                state["cash"] = round(cash - cost, 2)
                state["positions"][symbol] = {
                    "symbol": symbol,
                    "entry_at": day,
                    "entry_price": round(execution_price, 2),
                    "shares": shares,
                    "stop": round(execution_price - atr * STOP_ATR_MULTIPLIER, 2),
                    "target": round(execution_price + atr * TARGET_ATR_MULTIPLIER, 2),
                    "filter": asdict(selected_filter),
                    "score": score,
                    "score_details": score_details,
                    "buy_fee": round(fee, 2),
                }
                events.append({"day": day, "type": "buy", "symbol": symbol, "price": round(execution_price, 2), "shares": shares, "cost": cost, "score": score, "fee": round(fee, 2)})
                if len(state["positions"]) >= MAX_OPEN_POSITIONS:
                    break

        daily_values.append({"day": day, "value": _portfolio_value_at(state, prepared, i)})

    final_value = daily_values[-1]["value"] if daily_values else capital
    winning_trades = [trade for trade in state["closed_trades"] if float(trade["pnl"]) > 0]
    losing_trades = [trade for trade in state["closed_trades"] if float(trade["pnl"]) < 0]
    gross_profit = sum(float(trade["pnl"]) for trade in winning_trades)
    gross_loss = abs(sum(float(trade["pnl"]) for trade in losing_trades))
    peak = capital
    max_drawdown = 0.0
    for row in daily_values:
        peak = max(peak, float(row["value"]))
        if peak > 0:
            max_drawdown = min(max_drawdown, (float(row["value"]) / peak - 1) * 100)
    result = {
        "status": "completed",
        "initial_capital": round(capital, 2),
        "final_value": round(final_value, 2),
        "return_pct": round((final_value / capital - 1) * 100, 2),
        "symbols": sorted(prepared),
        "skipped": skipped,
        "days": len(daily_values),
        "last_calibration": last_calibration,
        "total_events": len(events),
        "buys": sum(1 for event in events if event["type"] == "buy"),
        "sells": sum(1 for event in events if event["type"] == "sell"),
        "partial_sells": sum(1 for event in events if event["type"] == "partial_sell"),
        "closed_trades": len(state["closed_trades"]),
        "win_rate_pct": round(len(winning_trades) / len(state["closed_trades"]) * 100, 2) if state["closed_trades"] else 0,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else (999 if gross_profit > 0 else 0),
        **risk_adjusted_metrics(daily_values),
        "max_drawdown_pct": round(max_drawdown, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "cash": round(float(state["cash"]), 2),
        "open_positions": state["positions"],
        "execution": {"cost_bps": COST_BPS, "slippage_bps": SLIPPAGE_BPS, "benchmark": BENCHMARK_SYMBOL},
        "events": events[-120:],
        "daily_values": daily_values[-120:],
    }
    _save_deep_replay(result)
    _log({"type": "deep_replay", **{key: result[key] for key in ["initial_capital", "final_value", "return_pct", "buys", "sells", "win_rate_pct"]}})
    return result


def main() -> None:
    interval = int(os.getenv("PAPER_SIM_INTERVAL_SECONDS", "300"))
    _log({"type": "startup", "interval_seconds": interval, "state_path": str(STATE_PATH), "events_path": str(EVENTS_PATH)})
    _log(
        {
            "type": "simulation_config",
            "ai_first_mode": AI_FIRST_MODE,
            "reliable_precision_target_pct": RELIABLE_PRECISION_PCT,
            "ai_first_min_precision_pct": AI_FIRST_MIN_PRECISION_PCT,
            "initial_capital": INITIAL_CAPITAL,
            "max_position_pct": MAX_POSITION_PCT,
            "max_open_positions": MAX_OPEN_POSITIONS,
        }
    )
    while True:
        try:
            evaluate_cycle()
        except Exception as exc:
            _log({"type": "error", "error": repr(exc)})
        time.sleep(interval)


if __name__ == "__main__":
    if os.getenv("PAPER_SIM_MODE") == "deep-replay":
        print(json.dumps(run_deep_replay(), ensure_ascii=False, indent=2))
    else:
        main()
