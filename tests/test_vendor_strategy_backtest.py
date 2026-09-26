from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from vendor_strategy_backtest import CostSpec, completed_mtf_side, simulate


def _frame() -> pd.DataFrame:
    index = pd.date_range("2025-01-02 14:30", periods=8, freq="5min", tz="UTC")
    frame = pd.DataFrame(
        {"open": [100, 100, 101, 102, 103, 104, 105, 106],
         "high": [101, 101, 103, 104, 105, 106, 107, 108],
         "low": [99, 99, 100, 101, 102, 103, 104, 105],
         "close": [100, 101, 102, 103, 104, 105, 106, 107],
         "atr": [1.0] * 8}, index=index)
    frame["date"] = index.tz_convert("America/New_York").date
    return frame


def test_signal_is_filled_only_at_next_bar_open():
    frame = _frame()
    signal = pd.Series(0, index=frame.index)
    signal.iloc[1] = 1
    trades = simulate(
        frame, signal, CostSpec(point_value=1, round_trip_cost=0),
        {"stop_atr": 1, "reward_r": 2, "hold_minutes": 30},
    )
    assert trades[0]["decision_time"] == frame.index[1].isoformat()
    assert trades[0]["entry"] == frame.open.iloc[2]


def test_stop_wins_when_stop_and_target_share_a_bar():
    frame = _frame()
    signal = pd.Series(0, index=frame.index)
    signal.iloc[1] = 1
    # Entry=101; the next bar spans 100..103, touching stop=100 and target=102.
    trades = simulate(
        frame, signal, CostSpec(point_value=1, round_trip_cost=0),
        {"stop_atr": 1, "reward_r": 1, "hold_minutes": 30},
    )
    assert trades[0]["reason"] == "stop"
    assert trades[0]["net_pnl"] == -1


def test_higher_timeframe_state_does_not_backfill_future_close():
    frame = _frame().drop(columns=["atr", "date"])
    side = completed_mtf_side(frame, "60min")
    # Fewer than 60 completed H1 observations: the higher-timeframe trend must
    # remain unavailable instead of being backfilled from a future candle.
    assert side.isna().all()
