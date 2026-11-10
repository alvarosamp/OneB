from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.intraday_setup_research import (
    DEFAULT_SPECS,
    ResearchConfig,
    build_features,
    diagnose_bars,
    load_intraday_csv,
    resample_bars,
    research_market,
    research_timeframes,
    setup_grid,
    setup_signals,
    simulate,
)


def _bars(days: int = 3) -> pd.DataFrame:
    pieces = []
    for day in pd.bdate_range("2026-01-05", periods=days):
        index = pd.date_range(
            f"{day.date()} 08:00", f"{day.date()} 16:00", freq="5min", tz="America/New_York", inclusive="left"
        )
        sequence = np.arange(len(index), dtype=float)
        close = 20000 + sequence * 0.05 + day.day
        pieces.append(
            pd.DataFrame(
                {"open": close - 0.05, "high": close + 0.30, "low": close - 0.30, "close": close, "volume": 100 + sequence},
                index=index,
            )
        )
    return pd.concat(pieces)


def test_loads_mt5_file_and_localizes_timezone():
    path = Path(__file__).parent / "fixtures" / "mt5_m1_sample.csv"
    bars = load_intraday_csv(path)
    assert bars.index.tz is not None
    assert bars.index[0].hour == 10
    assert bars.iloc[0]["volume"] == 0


def test_loads_epoch_milliseconds_and_preserves_bid_ask():
    path = Path(__file__).parent / "fixtures" / "epoch_bid_ask_sample.csv"
    bars = load_intraday_csv(path)
    assert bars.index[0] == pd.Timestamp("2025-03-18 20:00", tz="America/New_York")
    assert bars.iloc[0]["ask_open"] == 100.2


def test_feature_values_before_a_future_change_are_unchanged():
    original = _bars(3)
    changed = original.copy()
    cutoff = changed.index[150]
    changed.loc[cutoff:, ["open", "high", "low", "close"]] += 1000
    left = build_features(original, DEFAULT_SPECS["NQ"], 30)
    right = build_features(changed, DEFAULT_SPECS["NQ"], 30)
    columns = ["atr14", "ema20", "vwap", "opening_high", "overnight_high", "prior_session_close"]
    pd.testing.assert_frame_equal(left.loc[left.index < cutoff, columns], right.loc[right.index < cutoff, columns])


def test_execution_is_next_bar_and_includes_contract_costs():
    index = pd.date_range("2026-01-05 09:30", periods=50, freq="5min", tz="America/New_York")
    frame = pd.DataFrame({"open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0, "volume": 100.0}, index=index)
    frame["session_date"] = index.date
    frame["atr14"] = 1.0
    signal = pd.Series(False, index=index)
    signal.iloc[20] = True
    frame.iloc[21, frame.columns.get_loc("high")] = 102.1
    trades = simulate(frame, DEFAULT_SPECS["MNQ"], signal, signal & False, 1.0, 2.0, 30, "test")
    assert len(trades) == 1
    assert trades[0]["decision_time"] == index[20].isoformat()
    assert trades[0]["entry_time"] == index[21].isoformat()
    assert trades[0]["exit_reason"] == "target"
    assert trades[0]["net_pnl"] == 1.4


def test_observed_bid_ask_is_used_for_execution():
    index = pd.date_range("2026-01-05 09:30", periods=50, freq="5min", tz="America/New_York")
    frame = pd.DataFrame({"open": 100.1, "high": 100.3, "low": 99.9, "close": 100.1, "volume": 100.0}, index=index)
    frame["bid_open"] = 100.0
    frame["bid_high"] = 100.2
    frame["bid_low"] = 99.8
    frame["bid_close"] = 100.0
    frame["ask_open"] = 100.2
    frame["ask_high"] = 100.4
    frame["ask_low"] = 100.0
    frame["ask_close"] = 100.2
    frame["session_date"] = index.date
    frame["atr14"] = 1.0
    signal = pd.Series(False, index=index)
    signal.iloc[20] = True
    frame.iloc[21, frame.columns.get_loc("bid_high")] = 102.5
    trades = simulate(frame, DEFAULT_SPECS["MNQ"], signal, signal & False, 1.0, 2.0, 30, "quotes")
    assert trades[0]["execution_model"] == "observed_bid_ask"
    assert trades[0]["entry"] == 100.325
    assert trades[0]["net_pnl"] < 4.0


def test_research_blocks_short_history_instead_of_ranking_it():
    bars = _bars(10)
    config = replace(ResearchConfig(), min_sessions=250)
    result, tables = research_market(bars, DEFAULT_SPECS["NQ"], config)
    assert result["status"] == "NEEDS_MORE_DATA"
    assert "INSUFFICIENT_SESSIONS:10<250" in result["diagnostic"]["issues"]
    assert tables == {}


def test_quality_diagnostic_detects_invalid_ohlc():
    bars = _bars(1)
    bars.iloc[0, bars.columns.get_loc("high")] = bars.iloc[0]["low"] - 1
    result = diagnose_bars(bars)
    assert result["status"] == "BLOCKED"
    assert result["invalid_ohlc"] == 1


def test_small_grid_exercises_complete_research_path():
    bars = _bars(20)
    config = ResearchConfig(
        opening_ranges_minutes=(15,),
        stop_atr=(1.0,),
        reward_r=(2.0,),
        max_hold_minutes=(30,),
        holdout_fraction=0.2,
        development_folds=2,
        min_sessions=10,
        min_holdout_trades=3,
        final_candidates=2,
    )
    result, tables = research_market(bars, DEFAULT_SPECS["NQ"], config)
    assert result["status"] == "COMPLETE"
    assert result["holdout"]["sessions"] == 4
    assert set(tables) == {
        "entry_screening", "development", "holdout", "trades", "meta_labeling", "cost_sensitivity", "regime_holdout"
    }
    assert len(tables["holdout"]) == 2
    assert tables["cost_sensitivity"]["cost_multiplier"].tolist() == [1.0, 1.5, 2.0]


def test_named_strategy_families_from_user_document_are_registered():
    gold = {row["family"] for row in setup_grid(ResearchConfig(), "GC")}
    nasdaq = {row["family"] for row in setup_grid(ResearchConfig(), "NQ")}
    assert {"gold_fakeout", "gold_mean_reversion", "gold_trend_pullback", "gold_volatility_squeeze"} <= gold
    assert {"nasdaq_13x_sweep", "nasdaq_13x_ema_atr", "nasdaq_13x_momentum_failure"} <= nasdaq


def test_gold_fakeout_waits_for_confirmations():
    index = pd.date_range("2026-01-05 07:00", periods=30, freq="10min", tz="America/New_York")
    frame = pd.DataFrame({"open": 101.0, "high": 102.0, "low": 100.0, "close": 101.0}, index=index)
    frame["ma1000"] = 99.0
    frame["minutes_from_open"] = np.arange(30) * 10
    frame.iloc[22, frame.columns.get_loc("low")] = 99.0
    frame.iloc[22, frame.columns.get_loc("close")] = 100.5
    setup = {
        "family": "gold_fakeout", "lookback": 20, "ma_period": 1000,
        "confirmation_bars": 2, "stop_buffer_atr": 0.15, "structural_stop": True,
    }
    long_signal, _ = setup_signals(frame, DEFAULT_SPECS["GC"], setup)
    assert not long_signal.iloc[22]
    assert not long_signal.iloc[23]
    assert long_signal.iloc[24]


def test_structural_sweep_stop_uses_extreme_and_atr_buffer():
    index = pd.date_range("2026-01-05 09:30", periods=50, freq="5min", tz="America/New_York")
    frame = pd.DataFrame({"open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0, "volume": 100.0}, index=index)
    frame["session_date"] = index.date
    frame["atr14"] = 1.0
    frame.iloc[20, frame.columns.get_loc("low")] = 98.0
    long_signal = pd.Series(False, index=index)
    long_signal.iloc[20] = True
    setup = {"family": "nasdaq_13x_sweep", "confirmation_bars": 0, "stop_buffer_atr": 0.15, "structural_stop": True}
    trades = simulate(frame, DEFAULT_SPECS["MNQ"], long_signal, long_signal & False, None, 2.0, 30, "sweep", setup=setup)
    assert len(trades) == 1
    assert trades[0]["stop"] == 97.85


def test_resampling_and_timeframe_routes_are_deterministic():
    bars = _bars(2)
    ten_minute = resample_bars(bars, 10)
    assert diagnose_bars(ten_minute)["bar_minutes"] == 10
    assert research_timeframes("NQ", 1) == [1, 5, 10, 15]
    assert research_timeframes("NQ", 5) == [5, 10, 15]
    assert research_timeframes("GC", 5) == [10]
