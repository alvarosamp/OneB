from pathlib import Path

import pandas as pd

from scripts.validate_mtf_liquidity import confirmed_swings, load_bars, run_strategy


def test_confirmed_swing_is_delayed_until_right_bars_close():
    index = pd.date_range("2026-01-01", periods=9, freq="min")
    frame = pd.DataFrame({"high": [1, 2, 3, 9, 3, 2, 1, 2, 1], "low": [0] * 9, "close": [1] * 9}, index=index)
    highs, _ = confirmed_swings(frame, strength=2)
    assert highs.loc[index[5]] == 9
    assert highs.loc[index[3]] != 9


def test_load_mt5_date_and_time_columns():
    csv = Path(__file__).parent / "fixtures" / "mt5_m1_sample.csv"
    bars = load_bars(csv)
    assert bars.index[0] == pd.Timestamp("2026-01-02 10:00")
    assert bars.close.iloc[0] == 101


def test_strategy_returns_an_empty_but_valid_frame_when_no_setup():
    index = pd.date_range("2026-01-01", periods=500, freq="min")
    bars = pd.DataFrame({"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0}, index=index)
    signals = run_strategy(bars)
    assert list(signals.columns) == ["side", "entry"]
    assert signals.empty
