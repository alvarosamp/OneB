from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.market_data import macro_data
from app.models import GlobalNewsItem, MacroIntelligenceSnapshot
from app.regime_engine import (
    backfill_macro_intelligence_snapshots,
    macro_intelligence_history,
    market_news_context,
    news_market_relationships,
    store_macro_intelligence_snapshot,
)
from app.scheduler import build_scheduler


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def _history(ending: str = "2026-09-15") -> pd.DataFrame:
    index = pd.bdate_range(end=pd.Timestamp(ending, tz="UTC"), periods=100)
    close = pd.Series(100 + np.arange(100) * 0.25, index=index)
    frame = pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 1_000,
        },
        index=index,
    )
    frame.attrs["provider"] = "test"
    return frame


def _histories() -> dict[str, pd.DataFrame]:
    return {key: _history() for key in macro_data.TREND_WATCHLIST}


def test_daily_snapshot_is_idempotent_and_records_data_quality(db_session):
    first_time = datetime(2026, 9, 15, 21, tzinfo=timezone.utc)
    first = store_macro_intelligence_snapshot(db_session, histories=_histories(), captured_at=first_time)
    repeated = store_macro_intelligence_snapshot(
        db_session,
        histories=_histories(),
        captured_at=first_time + timedelta(hours=1),
    )

    assert repeated.id == first.id
    assert db_session.query(MacroIntelligenceSnapshot).count() == 1
    assert repeated.coverage_pct == 100.0
    assert repeated.fresh_count == len(macro_data.TREND_WATCHLIST)
    assert repeated.missing_count == 0
    assert repeated.payload["correlation_windows"]["60"]["matrix"]
    assert repeated.payload["daily_moves"]["NASDAQ"]["unit"] == "%"
    assert repeated.payload["daily_moves"]["US10Y"]["unit"] == "bps"
    assert repeated.payload["news_context"]["article_count"] == 0

    store_macro_intelligence_snapshot(
        db_session,
        histories=_histories(),
        captured_at=first_time + timedelta(days=1),
    )
    assert db_session.query(MacroIntelligenceSnapshot).count() == 2


def test_snapshot_date_uses_us_market_day_instead_of_utc_rollover(db_session):
    after_midnight_utc = datetime(2026, 9, 16, 1, 30, tzinfo=timezone.utc)

    snapshot = store_macro_intelligence_snapshot(
        db_session,
        histories=_histories(),
        captured_at=after_midnight_utc,
    )

    assert snapshot.snapshot_date == "2026-09-15"


def test_history_promotes_only_recurrent_lead_lag_hypotheses(db_session):
    start = datetime(2026, 9, 1, 21, tzinfo=timezone.utc)
    for offset in range(6):
        captured_at = start + timedelta(days=offset)
        db_session.add(
            MacroIntelligenceSnapshot(
                snapshot_date=captured_at.date().isoformat(),
                captured_at=captured_at,
                coverage_pct=100.0,
                fresh_count=12,
                stale_count=0,
                missing_count=0,
                payload={
                    "lead_lag_candidates": [
                        {
                            "leader": "US10Y",
                            "follower": "NASDAQ",
                            "lag_sessions": 2,
                            "correlation": -0.6,
                        }
                    ]
                },
            )
        )
    db_session.commit()

    result = macro_intelligence_history(db_session, limit=90)

    assert result["days_recorded"] == 6
    assert result["lead_lag_validation"] == [
        {
            "leader": "US10Y",
            "follower": "NASDAQ",
            "lag_sessions": 2,
            "observations_days": 6,
            "persistence_pct": 100.0,
            "average_correlation": -0.6,
            "last_seen": "2026-09-06",
            "status": "RECORRENTE",
        }
    ]


def test_news_context_separates_impact_sentiment_and_topics(db_session):
    captured_at = datetime(2026, 9, 15, 21, tzinfo=timezone.utc)
    db_session.add_all(
        [
            GlobalNewsItem(
                category="general",
                headline="Fed signals rate cut as inflation cools",
                summary="Technology shares rally after the FOMC decision.",
                url="https://example.test/fed",
                source="Test Wire",
                impact_score=70,
                sentiment_score=0.6,
                published_at=captured_at - timedelta(hours=2),
            ),
            GlobalNewsItem(
                category="general",
                headline="Oil rises as war threatens supply",
                summary="Brent and WTI react to geopolitical risk.",
                url="https://example.test/oil",
                source="Test Wire",
                impact_score=50,
                sentiment_score=-0.2,
                published_at=captured_at - timedelta(hours=4),
            ),
            GlobalNewsItem(
                category="general",
                headline="Old market story",
                summary="Outside the selected window.",
                url="https://example.test/old",
                source="Test Wire",
                impact_score=100,
                sentiment_score=1.0,
                published_at=captured_at - timedelta(hours=30),
            ),
            GlobalNewsItem(
                category="general",
                headline="Future market story",
                summary="Must not leak into the current snapshot.",
                url="https://example.test/future",
                source="Test Wire",
                impact_score=100,
                sentiment_score=1.0,
                published_at=captured_at + timedelta(minutes=1),
            ),
        ]
    )
    db_session.commit()

    context = market_news_context(db_session, captured_at=captured_at)

    assert context["article_count"] == 2
    assert context["high_impact_count"] == 2
    assert context["impact_sum"] == 120
    assert context["mean_sentiment"] == 0.2
    assert context["sentiment_coverage_pct"] == 100.0
    assert context["theme_counts"]["POLITICA_MONETARIA"] == 1
    assert context["theme_counts"]["INFLACAO"] == 1
    assert context["theme_counts"]["ENERGIA"] == 1
    assert context["theme_counts"]["GEOPOLITICA"] == 1


def test_news_market_analysis_uses_only_the_next_stored_session(db_session):
    start = datetime(2026, 8, 1, 21, tzinfo=timezone.utc)
    for offset in range(22):
        impact = float(offset + 1)
        sentiment = 1.0 if offset % 2 == 0 else -1.0
        previous_sentiment = 1.0 if (offset - 1) % 2 == 0 else -1.0
        move_size = float(max(offset, 1))
        db_session.add(
            MacroIntelligenceSnapshot(
                snapshot_date=(start + timedelta(days=offset)).date().isoformat(),
                captured_at=start + timedelta(days=offset),
                coverage_pct=100.0,
                fresh_count=12,
                stale_count=0,
                missing_count=0,
                payload={
                    "news_context": {
                        "article_count": 1,
                        "impact_sum": impact,
                        "mean_sentiment": sentiment,
                        "theme_counts": {"ENERGIA": impact},
                    },
                    "daily_moves": {
                        "WTI": {
                            "move": previous_sentiment * move_size,
                            "absolute_move": move_size,
                            "unit": "%",
                            "as_of": (start + timedelta(days=offset)).date().isoformat(),
                        }
                    },
                    "lead_lag_candidates": [],
                },
            )
        )
    db_session.commit()

    result = macro_intelligence_history(db_session, limit=90)["news_market_analysis"]
    intensity = next(row for row in result["correlations"] if row["factor"] == "INTENSIDADE_TOTAL")
    sentiment = next(row for row in result["correlations"] if row["factor"] == "SENTIMENTO_MEDIO")

    assert result["status"] == "PRONTO"
    assert result["available_forward_pairs"] == 21
    assert intensity["target"] == "MAGNITUDE"
    assert intensity["correlation"] == 1.0
    assert sentiment["target"] == "DIRECAO"
    assert sentiment["correlation"] > 0.8
    assert result["windows"]["3m"]["available_forward_pairs"] == 21
    assert result["windows"]["6m"]["expected_sessions_approx"] == 126
    assert result["windows"]["12m"]["expected_sessions_approx"] == 252


def test_news_market_analysis_waits_for_minimum_sample():
    start = datetime(2026, 9, 1, 21, tzinfo=timezone.utc)
    snapshots = [
        MacroIntelligenceSnapshot(
            snapshot_date=(start + timedelta(days=offset)).date().isoformat(),
            captured_at=start + timedelta(days=offset),
            payload={
                "news_context": {"article_count": 1, "impact_sum": offset + 1, "theme_counts": {}},
                "daily_moves": {
                    "GOLD": {
                        "move": offset,
                        "absolute_move": offset,
                        "unit": "%",
                        "as_of": (start + timedelta(days=offset)).date().isoformat(),
                    }
                },
            },
        )
        for offset in range(5)
    ]

    result = news_market_relationships(snapshots)

    assert result["status"] == "COLETANDO_HISTORICO"
    assert result["available_forward_pairs"] == 4
    assert result["correlations"] == []


def test_backfill_uses_point_in_time_prices_and_carries_weekend_news(db_session):
    friday_cutoff = datetime(2026, 8, 7, 21, tzinfo=timezone.utc)
    db_session.add(
        GlobalNewsItem(
            category="general",
            headline="Oil supply risk grows during weekend",
            summary="OPEC and geopolitical tensions affect crude markets.",
            url="https://example.test/weekend-oil",
            source="Test Wire",
            impact_score=60,
            published_at=friday_cutoff + timedelta(hours=24),
        )
    )
    db_session.commit()

    result = backfill_macro_intelligence_snapshots(
        db_session,
        histories=_histories(),
        start_date=datetime(2026, 8, 6).date(),
        end_date=datetime(2026, 8, 10).date(),
    )

    assert result["dates"] == ["2026-08-06", "2026-08-07", "2026-08-10"]
    snapshots = {
        row.snapshot_date: row
        for row in db_session.query(MacroIntelligenceSnapshot).order_by(MacroIntelligenceSnapshot.snapshot_date).all()
    }
    monday = snapshots["2026-08-10"].payload
    assert monday["news_context"]["article_count"] == 1
    assert monday["news_context"]["window_start"] == friday_cutoff.isoformat()
    assert monday["daily_moves"]["NASDAQ"]["as_of"].startswith("2026-08-10")
    assert all(
        row["as_of"][:10] <= snapshot_date
        for snapshot_date, snapshot in snapshots.items()
        for row in (snapshot.payload or {}).get("daily_moves", {}).values()
    )

    repeated = backfill_macro_intelligence_snapshots(
        db_session,
        histories=_histories(),
        start_date=datetime(2026, 8, 6).date(),
        end_date=datetime(2026, 8, 10).date(),
    )
    assert repeated["created"] == 0


def test_news_relationship_excludes_stale_market_moves():
    start = datetime(2026, 9, 1, 21, tzinfo=timezone.utc)
    snapshots = [
        MacroIntelligenceSnapshot(
            snapshot_date=(start + timedelta(days=offset)).date().isoformat(),
            captured_at=start + timedelta(days=offset),
            payload={
                "news_context": {"article_count": 1, "impact_sum": offset + 1},
                "daily_moves": {
                    "GOLD": {
                        "move": offset,
                        "absolute_move": offset,
                        "as_of": "2026-08-31T00:00:00+00:00",
                    }
                },
            },
        )
        for offset in range(3)
    ]

    result = news_market_relationships(snapshots)

    assert result["available_forward_pairs"] == 0
    assert result["correlations"] == []


def test_news_relationship_does_not_bridge_missing_weeks():
    first = datetime(2026, 9, 1, 21, tzinfo=timezone.utc)
    second = first + timedelta(days=10)
    snapshots = [
        MacroIntelligenceSnapshot(
            snapshot_date=first.date().isoformat(),
            captured_at=first,
            payload={"news_context": {"article_count": 2, "impact_sum": 50}},
        ),
        MacroIntelligenceSnapshot(
            snapshot_date=second.date().isoformat(),
            captured_at=second,
            payload={"daily_moves": {"WTI": {"move": 1.2, "absolute_move": 1.2, "as_of": second.date().isoformat()}}},
        ),
    ]

    assert news_market_relationships(snapshots)["available_forward_pairs"] == 0


def test_scheduler_registers_daily_macro_intelligence_job():
    scheduler = build_scheduler(None)

    job = scheduler.get_job("refresh_macro_intelligence")

    assert job is not None
    assert "mon-fri" in str(job.trigger)
