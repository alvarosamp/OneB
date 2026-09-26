from __future__ import annotations

import pandas as pd

from scripts.build_intraday_recommendation_cards import build_card


def test_future_broker_clock_blocks_trade_even_with_approved_research(tmp_path):
    path = tmp_path / "US100.s_M5_sample.csv.gz"
    start = pd.Timestamp("2026-09-25T12:00:00Z")
    times = pd.date_range(start, periods=300, freq="5min")
    bars = pd.DataFrame(
        {
            "timestamp": times,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "spread": 7,
        }
    )
    bars.to_csv(path, index=False, compression="gzip")
    research = {
        "family": "test_setup",
        "classification": "approved_for_paper_trading",
        "holdout": {"trades": 100, "profit_factor": 1.5, "expectancy": 1.0, "bh_q_value": 0.01},
    }
    as_of = pd.Timestamp("2026-09-25T15:00:00Z")
    card = build_card("US100.s", path, research, as_of)
    assert card["action"] == "NO_TRADE"
    assert card["entry_price"] is None
    assert card["data_health"]["fresh"] is False
    assert card["data_health"]["timestamp_ahead_minutes"] > 5
