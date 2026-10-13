import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_oos_dukascopy", ROOT / "scripts" / "run_oos_dukascopy.py")
oos = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oos)

RULE = {
    "setup": "gold_fakeout_open", "symbol": "XAUUSD.s", "timeframe_minutes": 10, "trend_sma": 20, "break_lookback": 5,
    "session_window_brt": ["00:00", "23:59"], "server_utc_offset_hours": 3, "target_r": 1.5, "max_hold_minutes": 60,
    "point": 0.01,
}
SPEC = {"feed_validation": {
    "period": {"from_inclusive": "2026-05-01", "to_exclusive": "2026-06-01"},
    "honorpro_offset_search_hours": [0, 1, 2, 3, 4],
    "criteria": {"m5_return_correlation_min": 0.95, "median_abs_close_diff_usd_max": 1.0,
                 "ready_signal_recall_min": 0.6, "ready_signal_tolerance_minutes": 20},
}}


def _utc_bars(n=9000, seed=5):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-04-25", periods=n, freq="5min")
    close = 2300 + np.cumsum(rng.normal(0, 1.0, n))
    opens = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(opens, close) + rng.uniform(0, 0.5, n)
    low = np.minimum(opens, close) - rng.uniform(0, 0.5, n)
    return pd.DataFrame({"open": opens, "high": high, "low": low, "close": close, "tick_volume": 1}, index=idx)


def test_feed_validation_recovers_server_offset_and_accepts_matching_feed():
    utc = _utc_bars()
    duka = utc.assign(spread_usd=0.2)
    honor = utc.copy()
    honor.index = honor.index + pd.Timedelta(hours=3)  # servidor UTC+3
    honor = honor.assign(spread=25, close=honor["close"] + 0.1, high=honor["high"] + 0.1, low=honor["low"] + 0.1, open=honor["open"] + 0.1)
    result = oos.validate_feed(duka, honor, RULE, SPEC)
    assert result["best_offset_hours"] == 3
    assert result["correlation"] > 0.99
    assert result["passed"], result["checks"]


def test_feed_validation_rejects_unrelated_feed():
    duka = _utc_bars(seed=1).assign(spread_usd=0.2)
    honor = _utc_bars(seed=2).assign(spread=25)
    result = oos.validate_feed(duka, honor, RULE, SPEC)
    assert result["passed"] is False
