"""Market regime engine — Level 1 (per-asset local regime) and Level 2
(cross-asset/macro overlay), as scoped in the platform architecture plan.

Deterministic and rule-based on purpose: this feeds the AI copilot and the
future confidence engine, and neither may originate its own price/trend
read — they consume this module's output instead. Weights below are
hand-picked defaults, not validated; app/backtest.py-style quant validation
against real outcomes should replace them before this drives real trading
decisions (tracked as a follow-up, not solved here).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import json
import math
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy.orm import Session

from app import indicators
from app.market_data import macro_data
from app.market_data import service as market_data_service
from app.models import GlobalNewsItem, MacroIntelligenceSnapshot, MacroSnapshot

LOCAL_REGIME_LABELS = ("STRONG BEAR", "BEAR", "NEUTRAL", "BULL", "STRONG BULL")

# Instruments considered when explaining the Nasdaq's macro context. Kept
# separate from the full MACRO_INSTRUMENTS registry because not every
# tracked instrument is a useful cross-check for every target asset.
NASDAQ_CROSS_ASSETS = ("DXY", "US10Y", "GOLD", "SP500", "WTI")

RELEVANCE_HIGH = 0.5
RELEVANCE_MEDIUM = 0.25
CORRELATION_WINDOWS = {"20": 20, "60": 60, "3m": 63, "6m": 126, "12m": 252}
NEWS_ANALYSIS_MONTHS = (3, 6, 12)
MARKET_TIMEZONE = ZoneInfo("America/New_York")
NEWS_LOOKBACK_HOURS = 24
NEWS_MARKET_MINIMUM_OBSERVATIONS = 20
NEWS_HIGH_IMPACT_THRESHOLD = 40
NEWS_THEMES = {
    "POLITICA_MONETARIA": (
        "fed", "fomc", "central bank", "banco central", "interest rate", "taxa de juros",
        "rate cut", "rate hike", "corte de juros", "alta de juros", "powell",
    ),
    "INFLACAO": ("inflation", "inflação", "cpi", "pce", "consumer prices", "preços ao consumidor"),
    "CRESCIMENTO": (
        "gdp", "pib", "growth", "crescimento", "recession", "recessão", "employment",
        "emprego", "payroll", "desemprego", "manufacturing", "industrial",
    ),
    "ENERGIA": ("oil", "crude", "brent", "wti", "opec", "petróleo", "energia", "natural gas"),
    "GEOPOLITICA": (
        "war", "guerra", "sanction", "sanção", "tariff", "tarifa", "conflict", "conflito",
        "ukraine", "ucrânia", "russia", "rússia", "iran", "israel", "china", "trade war",
    ),
    "TECNOLOGIA": (
        "nasdaq", "technology", "tecnologia", "semiconductor", "chip", "artificial intelligence",
        "inteligência artificial", "nvidia", "apple", "microsoft", "amazon", "meta",
    ),
}


@dataclass
class LocalRegime:
    label: str
    score: float
    factors: list[dict]


def _period_change(close: pd.Series, sessions: int, *, yield_series: bool) -> float | None:
    if len(close) <= sessions:
        return None
    latest = float(close.iloc[-1])
    previous = float(close.iloc[-sessions - 1])
    if yield_series:
        return round((latest - previous) * 100, 1)
    if previous == 0:
        return None
    return round((latest / previous - 1) * 100, 2)


def trend_analysis(history: pd.DataFrame, *, yield_series: bool = False) -> dict | None:
    """Compact, multi-horizon trend read for the macro watchlist.

    Yields are reported in basis points; prices, indices and FX in percent.
    This avoids presenting a 10 bp yield move as though it were a comparable
    percentage move in gold or Nasdaq.
    """
    clean = history.sort_index()
    local = local_regime(clean)
    if local is None:
        return None
    close = clean["close"].dropna()
    if len(close) < 55:
        return None
    ema20 = indicators.ema(close, 20)
    ema50 = indicators.ema(close, 50)
    adx = indicators.adx(clean["high"], clean["low"], clean["close"], 14)["adx"].iloc[-1]
    strength = "INDEFINIDA" if pd.isna(adx) else "FORTE" if adx >= 25 else "MODERADA" if adx >= 18 else "FRACA"
    direction = {
        "STRONG BULL": "ALTA FORTE",
        "BULL": "ALTA",
        "NEUTRAL": "LATERAL",
        "BEAR": "BAIXA",
        "STRONG BEAR": "BAIXA FORTE",
    }[local.label]
    last_timestamp = pd.Timestamp(close.index[-1])
    if last_timestamp.tzinfo is None:
        last_timestamp = last_timestamp.tz_localize("UTC")
    else:
        last_timestamp = last_timestamp.tz_convert("UTC")
    age_days = max(0, (datetime.now(timezone.utc) - last_timestamp.to_pydatetime()).days)
    return {
        "direction": direction,
        "score": local.score,
        "strength": strength,
        "adx14": None if pd.isna(adx) else round(float(adx), 1),
        "change_5d": _period_change(close, 5, yield_series=yield_series),
        "change_20d": _period_change(close, 20, yield_series=yield_series),
        "change_60d": _period_change(close, 60, yield_series=yield_series),
        "change_unit": "bps" if yield_series else "%",
        "last": round(float(close.iloc[-1]), 4),
        "ema20": round(float(ema20.iloc[-1]), 4),
        "ema50": round(float(ema50.iloc[-1]), 4),
        "as_of": last_timestamp.isoformat(),
        "age_days": age_days,
    }


def _daily_change_series(history: pd.DataFrame, *, yield_series: bool) -> pd.Series:
    """Comparable daily innovations indexed by normalized UTC session date."""
    if history.empty or "close" not in history:
        return pd.Series(dtype=float)
    close = pd.to_numeric(history["close"], errors="coerce").dropna().sort_index()
    if close.empty:
        return pd.Series(dtype=float)
    normalized_index = pd.to_datetime(close.index, utc=True, errors="coerce").normalize()
    valid = ~normalized_index.isna()
    close = pd.Series(close.to_numpy()[valid], index=normalized_index[valid], dtype=float)
    close = close.groupby(level=0).last().sort_index()
    completed_date = _last_completed_market_date()
    close = close[close.index.date <= completed_date]
    if yield_series:
        return close.diff().dropna()
    return close.pct_change(fill_method=None).replace([float("inf"), float("-inf")], pd.NA).dropna()


def _last_completed_market_date() -> date:
    now = datetime.now(MARKET_TIMEZONE)
    return now.date() if now.time() >= time(hour=17) else (now - timedelta(days=1)).date()


def _safe_correlation(left: pd.Series, right: pd.Series) -> float | None:
    if len(left) < 2 or left.nunique(dropna=True) < 2 or right.nunique(dropna=True) < 2:
        return None
    correlation = left.corr(right)
    return None if pd.isna(correlation) else float(correlation)


def macro_correlation_window(
    histories: dict[str, pd.DataFrame],
    *,
    keys: tuple[str, ...] = macro_data.TREND_WATCHLIST,
    sessions: int = 60,
) -> dict:
    """Pairwise rolling correlations across the complete macro watchlist.

    Price instruments use daily returns. Treasury yields use daily level
    changes, avoiding spurious correlations between non-stationary levels.
    Pairwise alignment preserves relationships when market holidays differ.
    """
    minimum_observations = max(8, math.ceil(sessions * (0.8 if sessions >= 63 else 0.6)))
    changes = {
        key: _daily_change_series(
            histories.get(key, pd.DataFrame()),
            yield_series=key.startswith("US") and key.endswith("Y"),
        )
        for key in keys
    }
    values: dict[str, dict[str, float | None]] = {key: {} for key in keys}
    pairs: list[dict] = []

    for left_index, left in enumerate(keys):
        for right_index, right in enumerate(keys):
            if left == right:
                enough = len(changes[left].tail(sessions)) >= minimum_observations
                values[left][right] = 1.0 if enough else None
                continue
            if right_index < left_index:
                values[left][right] = values[right][left]
                continue
            aligned = pd.concat([changes[left], changes[right]], axis=1, join="inner").dropna().tail(sessions)
            if len(aligned) < minimum_observations:
                correlation = None
            else:
                raw_correlation = _safe_correlation(aligned.iloc[:, 0], aligned.iloc[:, 1])
                correlation = None if raw_correlation is None else round(raw_correlation, 2)
            values[left][right] = correlation
            if correlation is not None:
                pairs.append(
                    {
                        "left": left,
                        "right": right,
                        "correlation": correlation,
                        "observations": int(len(aligned)),
                    }
                )

    ranked_positive = sorted((pair for pair in pairs if pair["correlation"] > 0), key=lambda row: row["correlation"], reverse=True)
    ranked_negative = sorted((pair for pair in pairs if pair["correlation"] < 0), key=lambda row: row["correlation"])
    return {
        "sessions": sessions,
        "minimum_observations": minimum_observations,
        "matrix": [{"key": key, "values": values[key]} for key in keys],
        "strongest_positive": ranked_positive[:5],
        "strongest_negative": ranked_negative[:5],
    }


def macro_correlation_analysis(histories: dict[str, pd.DataFrame]) -> dict[str, dict]:
    return {
        label: macro_correlation_window(histories, sessions=sessions)
        for label, sessions in CORRELATION_WINDOWS.items()
    }


def macro_relationship_dynamics(correlation_windows: dict[str, dict]) -> list[dict]:
    """Compare short and medium windows to expose unstable relationships."""
    short_window = correlation_windows.get("20")
    long_window = correlation_windows.get("60")
    if not short_window or not long_window:
        return []
    short_matrix = {row["key"]: row["values"] for row in short_window["matrix"]}
    long_matrix = {row["key"]: row["values"] for row in long_window["matrix"]}
    keys = [row["key"] for row in short_window["matrix"]]
    rows = []
    for left_index, left in enumerate(keys):
        for right in keys[left_index + 1 :]:
            recent = short_matrix.get(left, {}).get(right)
            baseline = long_matrix.get(left, {}).get(right)
            if recent is None or baseline is None:
                continue
            strength_delta = round(abs(recent) - abs(baseline), 2)
            if recent * baseline < 0 and abs(recent - baseline) >= 0.35:
                status = "INVERSAO"
            elif strength_delta >= 0.2:
                status = "FORTALECENDO"
            elif strength_delta <= -0.2:
                status = "ENFRAQUECENDO"
            else:
                status = "ESTAVEL"
            rows.append(
                {
                    "left": left,
                    "right": right,
                    "correlation_20d": recent,
                    "correlation_60d": baseline,
                    "delta": round(recent - baseline, 2),
                    "strength_delta": strength_delta,
                    "status": status,
                }
            )
    priority = {"INVERSAO": 3, "FORTALECENDO": 2, "ENFRAQUECENDO": 2, "ESTAVEL": 1}
    return sorted(rows, key=lambda row: (priority[row["status"]], abs(row["delta"])), reverse=True)


def macro_lead_lag_candidates(
    histories: dict[str, pd.DataFrame],
    *,
    keys: tuple[str, ...] = macro_data.TREND_WATCHLIST,
    sessions: int = 60,
    max_lag: int = 3,
) -> list[dict]:
    """Exploratory lead/lag scan; it deliberately makes no causal claim."""
    minimum_observations = max(20, math.ceil(sessions * 0.6))
    changes = {
        key: _daily_change_series(
            histories.get(key, pd.DataFrame()),
            yield_series=key.startswith("US") and key.endswith("Y"),
        )
        for key in keys
    }
    candidates: list[dict] = []
    for left_index, left in enumerate(keys):
        for right in keys[left_index + 1 :]:
            pair = pd.concat([changes[left], changes[right]], axis=1, join="outer").sort_index()
            pair.columns = [left, right]
            contemporaneous_data = pair.dropna().tail(sessions)
            if len(contemporaneous_data) < minimum_observations:
                continue
            contemporaneous = _safe_correlation(contemporaneous_data[left], contemporaneous_data[right])
            contemporaneous_abs = 0.0 if contemporaneous is None else abs(contemporaneous)
            contemporaneous_value = None if contemporaneous is None else round(contemporaneous, 2)
            best: dict | None = None
            for leader, follower in ((left, right), (right, left)):
                for lag in range(1, max_lag + 1):
                    aligned = pd.concat([pair[leader].shift(lag), pair[follower]], axis=1).dropna().tail(sessions)
                    if len(aligned) < minimum_observations:
                        continue
                    correlation = _safe_correlation(aligned.iloc[:, 0], aligned.iloc[:, 1])
                    if correlation is None:
                        continue
                    candidate = {
                        "leader": leader,
                        "follower": follower,
                        "lag_sessions": lag,
                        "correlation": round(correlation, 2),
                        "contemporaneous_correlation": contemporaneous_value,
                        "improvement": round(abs(correlation) - contemporaneous_abs, 2),
                        "observations": int(len(aligned)),
                    }
                    if best is None or abs(candidate["correlation"]) > abs(best["correlation"]):
                        best = candidate
            if best and abs(best["correlation"]) >= 0.35 and best["improvement"] >= 0.1:
                candidates.append(best)
    return sorted(candidates, key=lambda row: (row["improvement"], abs(row["correlation"])), reverse=True)[:10]


def collect_macro_histories(*, refresh: bool = False) -> dict[str, pd.DataFrame]:
    """Fetch every instrument independently so one provider failure is isolated."""
    histories = {}
    for key in macro_data.MACRO_INSTRUMENTS:
        try:
            histories[key] = macro_data.get_macro_history(key, period="1y", interval="1d", refresh=refresh)
        except Exception:
            histories[key] = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    return histories


def macro_data_quality(histories: dict[str, pd.DataFrame], *, captured_at: datetime) -> dict:
    instruments = []
    counts = {"FRESH": 0, "STALE": 0, "MISSING": 0}
    for key in macro_data.TREND_WATCHLIST:
        history = histories.get(key, pd.DataFrame())
        if history.empty:
            status = "MISSING"
            rows = 0
            as_of = None
            age_days = None
            provider = None
            cache_fallback = False
        else:
            timestamp = pd.Timestamp(history.index[-1])
            if timestamp.tzinfo is None:
                timestamp = timestamp.tz_localize("UTC")
            else:
                timestamp = timestamp.tz_convert("UTC")
            age_days = max(0, (captured_at - timestamp.to_pydatetime()).days)
            status = "FRESH" if age_days <= 4 else "STALE"
            rows = int(len(history))
            as_of = timestamp.isoformat()
            provider = history.attrs.get("provider")
            cache_fallback = bool(history.attrs.get("cache_fallback", False))
        counts[status] += 1
        instruments.append(
            {
                "key": key,
                "status": status,
                "rows": rows,
                "as_of": as_of,
                "age_days": age_days,
                "provider": provider,
                "cache_fallback": cache_fallback,
            }
        )
    total = len(macro_data.TREND_WATCHLIST)
    usable = counts["FRESH"] + counts["STALE"]
    return {
        "coverage_pct": round(usable / total * 100, 1) if total else 0.0,
        "fresh_count": counts["FRESH"],
        "stale_count": counts["STALE"],
        "missing_count": counts["MISSING"],
        "instruments": instruments,
    }


def _news_themes(headline: str, summary: str = "") -> list[str]:
    text = f"{headline} {summary}".lower()
    return [theme for theme, terms in NEWS_THEMES.items() if any(term in text for term in terms)]


def market_news_context(
    db: Session,
    *,
    captured_at: datetime | None = None,
    lookback_hours: int = NEWS_LOOKBACK_HOURS,
    window_start: datetime | None = None,
) -> dict:
    """Summarize only news known before the snapshot cutoff.

    Impact is an unsigned relevance/intensity score. It must not be treated as
    bullish or bearish; direction is sourced only from explicit sentiment.
    """
    captured_at = captured_at or datetime.now(timezone.utc)
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    window_start = window_start or captured_at - timedelta(hours=lookback_hours)
    if window_start.tzinfo is None:
        window_start = window_start.replace(tzinfo=timezone.utc)
    rows = (
        db.query(GlobalNewsItem)
        .filter(GlobalNewsItem.published_at > window_start)
        .filter(GlobalNewsItem.published_at <= captured_at)
        .order_by(GlobalNewsItem.impact_score.desc(), GlobalNewsItem.published_at.desc())
        .all()
    )
    impacts = [max(0, int(row.impact_score or 0)) for row in rows]
    sentiments = [float(row.sentiment_score) for row in rows if row.sentiment_score is not None]
    theme_counts = {theme: 0 for theme in NEWS_THEMES}
    for row in rows:
        for theme in _news_themes(row.headline, row.summary or ""):
            theme_counts[theme] += 1
    active_themes = {theme: count for theme, count in theme_counts.items() if count}
    return {
        "window_start": window_start.isoformat(),
        "window_end": captured_at.isoformat(),
        "lookback_hours": round((captured_at - window_start).total_seconds() / 3600, 1),
        "article_count": len(rows),
        "high_impact_count": sum(impact >= NEWS_HIGH_IMPACT_THRESHOLD for impact in impacts),
        "impact_sum": sum(impacts),
        "average_impact": round(sum(impacts) / len(impacts), 1) if impacts else None,
        "maximum_impact": max(impacts) if impacts else None,
        "mean_sentiment": round(sum(sentiments) / len(sentiments), 4) if sentiments else None,
        "sentiment_observations": len(sentiments),
        "sentiment_coverage_pct": round(len(sentiments) / len(rows) * 100, 1) if rows else 0.0,
        "theme_counts": active_themes,
        "top_headlines": [
            {
                "headline": row.headline,
                "source": row.source,
                "impact_score": int(row.impact_score or 0),
                "sentiment_score": row.sentiment_score,
                "published_at": row.published_at.isoformat(),
                "url": row.url,
            }
            for row in rows[:5]
        ],
        "methodology": "impacto mede intensidade; sentimento mede direcao quando disponivel",
    }


def macro_daily_moves(histories: dict[str, pd.DataFrame]) -> dict[str, dict]:
    """Latest daily innovation, persisted for forward news validation."""
    moves: dict[str, dict] = {}
    for key in macro_data.TREND_WATCHLIST:
        yield_series = key.startswith("US") and key.endswith("Y")
        changes = _daily_change_series(histories.get(key, pd.DataFrame()), yield_series=yield_series)
        if changes.empty:
            continue
        value = float(changes.iloc[-1]) * 100
        moves[key] = {
            "move": round(value, 4),
            "absolute_move": round(abs(value), 4),
            "unit": "bps" if yield_series else "%",
            "as_of": pd.Timestamp(changes.index[-1]).isoformat(),
        }
    return moves


def build_macro_intelligence_payload(
    histories: dict[str, pd.DataFrame],
    *,
    captured_at: datetime | None = None,
    news_context: dict | None = None,
) -> dict:
    captured_at = captured_at or datetime.now(timezone.utc)
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    correlations = macro_correlation_analysis(histories)
    trends = {
        key: trend_analysis(
            histories.get(key, pd.DataFrame()),
            yield_series=key.startswith("US") and key.endswith("Y"),
        )
        for key in macro_data.TREND_WATCHLIST
    }
    payload = {
        "version": 1,
        "captured_at": captured_at.isoformat(),
        "trends": trends,
        "correlation_windows": correlations,
        "relationship_dynamics": macro_relationship_dynamics(correlations),
        "lead_lag_candidates": macro_lead_lag_candidates(histories),
        "data_quality": macro_data_quality(histories, captured_at=captured_at),
        "daily_moves": macro_daily_moves(histories),
        "news_context": news_context,
    }
    return json.loads(json.dumps(payload, default=lambda value: value.item() if hasattr(value, "item") else str(value)))


def store_macro_intelligence_snapshot(
    db: Session,
    *,
    histories: dict[str, pd.DataFrame] | None = None,
    captured_at: datetime | None = None,
    refresh: bool = True,
) -> MacroIntelligenceSnapshot:
    """Upsert the daily cross-asset state; reruns never duplicate a day."""
    captured_at = captured_at or datetime.now(timezone.utc)
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    histories = histories if histories is not None else collect_macro_histories(refresh=refresh)
    snapshot_date = captured_at.astimezone(MARKET_TIMEZONE).date().isoformat()
    previous_snapshot = (
        db.query(MacroIntelligenceSnapshot)
        .filter(MacroIntelligenceSnapshot.snapshot_date < snapshot_date)
        .order_by(MacroIntelligenceSnapshot.snapshot_date.desc())
        .first()
    )
    news_window_start = previous_snapshot.captured_at if previous_snapshot is not None else None
    news_context = market_news_context(db, captured_at=captured_at, window_start=news_window_start)
    payload = build_macro_intelligence_payload(histories, captured_at=captured_at, news_context=news_context)
    quality = payload["data_quality"]
    snapshot = (
        db.query(MacroIntelligenceSnapshot)
        .filter(MacroIntelligenceSnapshot.snapshot_date == snapshot_date)
        .first()
    )
    if snapshot is None:
        snapshot = MacroIntelligenceSnapshot(snapshot_date=snapshot_date)
        db.add(snapshot)
    snapshot.captured_at = captured_at
    snapshot.coverage_pct = quality["coverage_pct"]
    snapshot.fresh_count = quality["fresh_count"]
    snapshot.stale_count = quality["stale_count"]
    snapshot.missing_count = quality["missing_count"]
    snapshot.payload = payload
    db.commit()
    db.refresh(snapshot)
    return snapshot


def _history_through_session(history: pd.DataFrame, session_date: date) -> pd.DataFrame:
    if history.empty:
        return history.copy()
    index = pd.to_datetime(history.index, utc=True, errors="coerce")
    mask = (~index.isna()) & (index.date <= session_date)
    sliced = history.loc[mask].copy()
    sliced.attrs.update(history.attrs)
    return sliced


def backfill_macro_intelligence_snapshots(
    db: Session,
    *,
    histories: dict[str, pd.DataFrame] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """Rebuild missing daily snapshots without allowing future prices or news."""
    histories = histories if histories is not None else collect_macro_histories(refresh=False)
    reference = histories.get("NASDAQ", pd.DataFrame())
    if reference.empty:
        return {"created": 0, "dates": [], "reason": "sem_historico_de_referencia"}
    oldest_news = db.query(GlobalNewsItem).order_by(GlobalNewsItem.published_at.asc()).first()
    if oldest_news is None and start_date is None:
        return {"created": 0, "dates": [], "reason": "sem_noticias_arquivadas"}
    start_date = start_date or oldest_news.published_at.date()
    completed_date = _last_completed_market_date()
    end_date = min(end_date or completed_date, completed_date)
    existing_dates = {value for (value,) in db.query(MacroIntelligenceSnapshot.snapshot_date).all()}
    reference_dates = sorted(
        {
            timestamp.date()
            for timestamp in pd.to_datetime(reference.index, utc=True, errors="coerce")
            if not pd.isna(timestamp) and start_date <= timestamp.date() <= end_date
        }
    )
    created = []
    for session_date in reference_dates:
        snapshot_date = session_date.isoformat()
        if snapshot_date in existing_dates:
            continue
        session_cutoff = datetime.combine(session_date, time(hour=21), tzinfo=timezone.utc)
        point_in_time_histories = {
            key: _history_through_session(history, session_date)
            for key, history in histories.items()
        }
        store_macro_intelligence_snapshot(
            db,
            histories=point_in_time_histories,
            captured_at=session_cutoff,
            refresh=False,
        )
        existing_dates.add(snapshot_date)
        created.append(snapshot_date)
    return {"created": len(created), "dates": created, "reason": None}


def news_market_relationships(
    snapshots: list[MacroIntelligenceSnapshot],
    *,
    minimum_observations: int = NEWS_MARKET_MINIMUM_OBSERVATIONS,
    include_windows: bool = True,
) -> dict:
    """Relate news at t only to market movement at the next stored session.

    News intensity and themes are compared with absolute movement. Signed
    returns are used only for explicit sentiment, preventing an unsigned
    impact score from being misrepresented as bullish or bearish.
    """
    ordered = sorted(snapshots, key=lambda row: row.snapshot_date)
    observations: dict[tuple[str, str, str, str], list[tuple[float, float]]] = {}
    available_forward_pairs = 0
    news_days = 0
    for snapshot in ordered:
        if ((snapshot.payload or {}).get("news_context") or {}).get("article_count"):
            news_days += 1
    for previous, current in zip(ordered, ordered[1:]):
        if (date.fromisoformat(current.snapshot_date) - date.fromisoformat(previous.snapshot_date)).days > 4:
            continue
        news = (previous.payload or {}).get("news_context") or {}
        moves = (current.payload or {}).get("daily_moves") or {}
        if not news.get("article_count") or not moves:
            continue
        current_session_moves = {
            asset: move
            for asset, move in moves.items()
            if str(move.get("as_of", ""))[:10] == current.snapshot_date
        }
        if not current_session_moves:
            continue
        available_forward_pairs += 1
        factors: list[tuple[str, str, float, str]] = []
        impact_sum = news.get("impact_sum")
        if impact_sum is not None:
            factors.append(("INTENSIDADE", "INTENSIDADE_TOTAL", float(impact_sum), "absolute_move"))
        sentiment = news.get("mean_sentiment")
        if sentiment is not None:
            factors.append(("SENTIMENTO", "SENTIMENTO_MEDIO", float(sentiment), "move"))
        for theme, count in (news.get("theme_counts") or {}).items():
            factors.append(("TEMA", str(theme), float(count), "absolute_move"))
        # A theme absent from a news-filled day is a real zero, not missing data.
        observed_themes = set((news.get("theme_counts") or {}).keys())
        for theme in NEWS_THEMES:
            if theme not in observed_themes:
                factors.append(("TEMA", theme, 0.0, "absolute_move"))
        for asset, move in current_session_moves.items():
            for factor_type, factor, factor_value, target in factors:
                target_value = move.get(target)
                if target_value is None:
                    continue
                identity = (factor_type, factor, asset, target)
                observations.setdefault(identity, []).append((factor_value, float(target_value)))

    correlations = []
    for (factor_type, factor, asset, target), pairs in observations.items():
        if len(pairs) < minimum_observations:
            continue
        frame = pd.DataFrame(pairs, columns=["factor", "market"])
        correlation = _safe_correlation(frame["factor"], frame["market"])
        if correlation is None:
            continue
        correlations.append(
            {
                "factor_type": factor_type,
                "factor": factor,
                "asset": asset,
                "target": "MAGNITUDE" if target == "absolute_move" else "DIRECAO",
                "correlation": round(correlation, 2),
                "observations": len(pairs),
                "direction": "POSITIVA" if correlation >= 0 else "NEGATIVA",
                "status": "EXPLORATORIO",
            }
        )
    correlations.sort(key=lambda row: abs(row["correlation"]), reverse=True)
    result = {
        "method": "noticias_t_para_movimento_na_coleta_seguinte",
        "minimum_observations": minimum_observations,
        "available_forward_pairs": available_forward_pairs,
        "sessions_recorded": len(ordered),
        "news_days": news_days,
        "coverage_pct": round(news_days / len(ordered) * 100, 1) if ordered else 0.0,
        "status": "PRONTO" if available_forward_pairs >= minimum_observations else "COLETANDO_HISTORICO",
        "correlations": correlations[:30],
        "warnings": [
            "correlacao nao implica causalidade",
            "impacto e temas sao comparados com magnitude; apenas sentimento e comparado com direcao",
            "resultados envolvem multiplos testes e exigem validacao fora da amostra",
        ],
    }
    if include_windows:
        latest_date = pd.Timestamp(ordered[-1].snapshot_date) if ordered else None
        result["windows"] = {
            f"{months}m": news_market_relationships(
                [
                    snapshot for snapshot in ordered
                    if pd.Timestamp(snapshot.snapshot_date) >= latest_date - pd.DateOffset(months=months)
                ],
                minimum_observations=minimum_observations,
                include_windows=False,
            )
            for months in NEWS_ANALYSIS_MONTHS
        } if latest_date is not None else {}
        for months in NEWS_ANALYSIS_MONTHS:
            window = result["windows"].get(f"{months}m")
            if window is None:
                continue
            expected_sessions = months * 21
            window["expected_sessions_approx"] = expected_sessions
            window["session_coverage_pct"] = round(
                min(window["sessions_recorded"] / expected_sessions * 100, 100), 1
            )
    return result


def macro_intelligence_history(db: Session, *, limit: int = 90) -> dict:
    snapshots = (
        db.query(MacroIntelligenceSnapshot)
        .order_by(MacroIntelligenceSnapshot.snapshot_date.desc())
        .limit(limit)
        .all()
    )
    occurrences: dict[tuple[str, str, int], dict] = {}
    for snapshot in snapshots:
        for candidate in (snapshot.payload or {}).get("lead_lag_candidates", []):
            identity = (candidate["leader"], candidate["follower"], int(candidate["lag_sessions"]))
            aggregate = occurrences.setdefault(
                identity,
                {"count": 0, "correlations": [], "last_seen": snapshot.snapshot_date},
            )
            aggregate["count"] += 1
            aggregate["correlations"].append(float(candidate["correlation"]))
            aggregate["last_seen"] = max(aggregate["last_seen"], snapshot.snapshot_date)
    total = len(snapshots)
    validation = []
    for (leader, follower, lag), aggregate in occurrences.items():
        persistence = round(aggregate["count"] / total * 100, 1) if total else 0.0
        validation.append(
            {
                "leader": leader,
                "follower": follower,
                "lag_sessions": lag,
                "observations_days": aggregate["count"],
                "persistence_pct": persistence,
                "average_correlation": round(sum(aggregate["correlations"]) / aggregate["count"], 2),
                "last_seen": aggregate["last_seen"],
                "status": "RECORRENTE" if aggregate["count"] >= 5 and persistence >= 30 else "OBSERVACAO",
            }
        )
    validation.sort(key=lambda row: (row["observations_days"], abs(row["average_correlation"])), reverse=True)
    return {
        "days_recorded": total,
        "lead_lag_validation": validation,
        "news_market_analysis": news_market_relationships(snapshots),
        "snapshots": [
            {
                "snapshot_date": snapshot.snapshot_date,
                "captured_at": snapshot.captured_at.isoformat(),
                "coverage_pct": snapshot.coverage_pct,
                "fresh_count": snapshot.fresh_count,
                "stale_count": snapshot.stale_count,
                "missing_count": snapshot.missing_count,
                "payload": snapshot.payload,
            }
            for snapshot in snapshots
        ],
    }


def local_regime(history: pd.DataFrame) -> LocalRegime | None:
    """Classifies trend/momentum/volatility/structure into one of
    LOCAL_REGIME_LABELS. `history` needs open/high/low/close columns (as
    returned by yfinance_client.get_history), ideally 60+ bars.
    """
    if history.empty or len(history) < 55:
        return None

    close, high, low = history["close"], history["high"], history["low"]
    ema20 = indicators.ema(close, 20)
    ema50 = indicators.ema(close, 50)
    rsi = indicators.rsi(close, 14)
    adx_df = indicators.adx(high, low, close, 14)
    swings = indicators.swing_levels(history, lookback=20)

    last_ema20, last_ema50 = ema20.iloc[-1], ema50.iloc[-1]
    last_rsi = rsi.iloc[-1]
    last_adx = adx_df["adx"].iloc[-1]
    last_close = float(close.iloc[-1])

    if pd.isna(last_ema20) or pd.isna(last_ema50) or pd.isna(last_rsi):
        return None

    factors = []
    score = 0.0

    trend_up = last_ema20 > last_ema50
    score += 30 if trend_up else -30
    factors.append(
        {
            "name": "trend",
            "impact": 30 if trend_up else -30,
            "evidence": f"EMA20 {'acima' if trend_up else 'abaixo'} da EMA50 ({last_ema20:.2f} vs {last_ema50:.2f}).",
        }
    )

    momentum_impact = max(-25.0, min(25.0, (last_rsi - 50) * 0.7))
    score += momentum_impact
    factors.append({"name": "momentum", "impact": round(momentum_impact, 1), "evidence": f"RSI14 em {last_rsi:.1f}."})

    if not pd.isna(last_adx):
        strong_trend = last_adx >= 25
        multiplier = 1.25 if strong_trend else 0.7
        score *= multiplier
        factors.append(
            {
                "name": "forca_da_tendencia",
                "impact": None,
                "evidence": f"ADX14 em {last_adx:.1f} ({'tendencia forte' if strong_trend else 'sem tendencia definida'}), "
                f"amplifica o score em {multiplier:.2f}x.",
            }
        )

    swing_high, swing_low = swings["swing_high"], swings["swing_low"]
    if swing_high and last_close >= swing_high * 0.995:
        score += 15
        factors.append({"name": "estrutura", "impact": 15, "evidence": f"Preco proximo/rompendo maxima de 20 candles ({swing_high})."})
    elif swing_low and last_close <= swing_low * 1.005:
        score -= 15
        factors.append({"name": "estrutura", "impact": -15, "evidence": f"Preco proximo/rompendo minima de 20 candles ({swing_low})."})

    score = max(-100.0, min(100.0, score))
    if score >= 60:
        label = "STRONG BULL"
    elif score >= 20:
        label = "BULL"
    elif score <= -60:
        label = "STRONG BEAR"
    elif score <= -20:
        label = "BEAR"
    else:
        label = "NEUTRAL"

    return LocalRegime(label=label, score=round(score, 1), factors=factors)


def store_macro_snapshots(db: Session) -> int:
    """Fetches the current quote for every MACRO_INSTRUMENTS entry and
    records it. Called by the scheduler; also safe to call ad hoc.
    Returns how many were stored.
    """
    stored = 0
    for key in macro_data.MACRO_INSTRUMENTS:
        quote = macro_data.get_macro_quote(key)
        if quote is None:
            continue
        db.add(
            MacroSnapshot(
                key=key,
                symbol=quote.symbol,
                name=quote.name,
                price=quote.price,
                change_pct=quote.change_pct,
            )
        )
        stored += 1
    db.commit()
    return stored


def latest_macro_snapshot(db: Session, key: str) -> MacroSnapshot | None:
    return db.query(MacroSnapshot).filter(MacroSnapshot.key == key).order_by(MacroSnapshot.taken_at.desc()).first()


def cross_asset_relevance(db: Session, target_key: str = "NASDAQ", lookback_days: int = 30) -> list[dict]:
    """Rolling-correlation read of which cross-asset instruments currently
    matter to `target_key`. Not a fixed rulebook ("oil down = stocks up") —
    correlation and confirming/opposing direction are computed fresh from
    the last `lookback_days` of daily returns each call.
    """
    target_history = macro_data.get_macro_history(target_key, period="6mo", interval="1d")
    if target_history.empty or len(target_history) < lookback_days + 5:
        return []
    target_returns = target_history["close"].pct_change().dropna()
    target_snapshot = latest_macro_snapshot(db, target_key)

    rows = []
    for key in NASDAQ_CROSS_ASSETS:
        if key == target_key:
            continue
        other_history = macro_data.get_macro_history(key, period="6mo", interval="1d")
        if other_history.empty or len(other_history) < lookback_days + 5:
            continue
        other_returns = other_history["close"].pct_change().dropna()

        aligned = pd.concat([target_returns, other_returns], axis=1, join="inner").tail(lookback_days)
        aligned.columns = ["target", "other"]
        if len(aligned) < lookback_days * 0.6:
            continue
        corr = aligned["target"].corr(aligned["other"])
        if pd.isna(corr):
            continue

        abs_corr = abs(corr)
        if abs_corr >= RELEVANCE_HIGH:
            relevance = "ALTA"
        elif abs_corr >= RELEVANCE_MEDIUM:
            relevance = "MEDIA"
        else:
            relevance = "BAIXA"

        other_snapshot = latest_macro_snapshot(db, key)
        direction = None
        if target_snapshot and other_snapshot and abs_corr >= RELEVANCE_MEDIUM:
            same_direction_today = (target_snapshot.change_pct >= 0) == (other_snapshot.change_pct >= 0)
            expected_same_direction = corr >= 0
            direction = "CONFIRMANDO" if same_direction_today == expected_same_direction else "DIVERGINDO"

        rows.append(
            {
                "key": key,
                "name": other_snapshot.name if other_snapshot else key,
                "correlation_30d": round(float(corr), 2),
                "relevance": relevance,
                "direction": direction,
                "change_pct_latest": other_snapshot.change_pct if other_snapshot else None,
            }
        )

    return sorted(rows, key=lambda r: abs(r["correlation_30d"]), reverse=True)


def macro_context_label(cross_asset: list[dict]) -> str:
    """Rolls the cross-asset relevance table up into one POSITIVO/NEUTRO/
    NEGATIVO label for the copilot header — only instruments flagged ALTA
    or MEDIA relevance vote; a target with no relevant instruments yet
    (cold cache) reads as NEUTRO rather than a false negative.
    """
    votes = [row for row in cross_asset if row["relevance"] in ("ALTA", "MEDIA") and row["direction"]]
    if not votes:
        return "NEUTRO"
    confirming = sum(1 for v in votes if v["direction"] == "CONFIRMANDO")
    diverging = len(votes) - confirming
    if confirming > diverging:
        return "POSITIVO"
    if diverging > confirming:
        return "NEGATIVO"
    return "NEUTRO"


def regime_report(db: Session, symbol: str) -> dict:
    """Combines local regime (this symbol's own price action) with the
    macro/cross-asset overlay. `symbol` can be an equity ticker (fetched
    directly via yfinance) or a MACRO_INSTRUMENTS key (e.g. "NASDAQ").
    """
    symbol_key = symbol.upper().strip()
    if symbol_key in macro_data.MACRO_INSTRUMENTS:
        history = macro_data.get_macro_history(symbol_key, period="6mo", interval="1d")
        target_key_for_macro = symbol_key
    else:
        history = market_data_service.get_bars(symbol_key, period="6mo", interval="1d")
        target_key_for_macro = "NASDAQ"

    local = local_regime(history)
    cross_asset = cross_asset_relevance(db, target_key=target_key_for_macro)

    return {
        "symbol": symbol_key,
        "local_regime": {"label": local.label, "score": local.score, "factors": local.factors} if local else None,
        "macro_context": macro_context_label(cross_asset),
        "cross_asset_relevance": cross_asset,
    }
