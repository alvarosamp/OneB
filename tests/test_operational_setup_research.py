from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.operational_setup_research import indicator_state, rule_candidates, rule_signals, simulate_trades


def _history(rows: int = 500) -> pd.DataFrame:
    index = pd.bdate_range("2020-01-01", periods=rows, tz="UTC")
    close = pd.Series(100 + np.linspace(0, 30, rows) + np.sin(np.arange(rows) / 5), index=index)
    return pd.DataFrame({"open": close.shift(1).fillna(close.iloc[0]), "high": close + 1, "low": close - 1, "close": close, "volume": 1_000_000}, index=index)


def test_rule_signals_are_causal():
    history = _history()
    candidate = next(row for row in rule_candidates() if row["family"] == "breakout")
    original = rule_signals(history, indicator_state(history), candidate)
    changed = history.copy()
    changed.iloc[400:, changed.columns.get_loc("close")] *= 2
    perturbed = rule_signals(changed, indicator_state(changed), candidate)
    pd.testing.assert_series_equal(original[0].iloc[:400], perturbed[0].iloc[:400])
    pd.testing.assert_series_equal(original[1].iloc[:400], perturbed[1].iloc[:400])


def test_ambiguous_bar_uses_stop_first():
    history = _history(100)
    state = indicator_state(history)
    decision = 60
    history.iloc[decision + 1, history.columns.get_loc("open")] = 100
    history.iloc[decision + 1, history.columns.get_loc("high")] = 110
    history.iloc[decision + 1, history.columns.get_loc("low")] = 90
    long_signal = pd.Series(False, index=history.index)
    short_signal = pd.Series(False, index=history.index)
    long_signal.iloc[decision] = True
    trades = simulate_trades(history, state["atr14"], long_signal, short_signal, history.index[decision], history.index[80], {"stop_atr": 1.0, "target_atr": 1.0, "max_hold": 5}, "long", 0, "test")
    assert trades[0]["exit_reason"] == "stop"
    assert trades[0]["net_return"] < 0


def test_signal_enters_on_next_open():
    history = _history(100)
    state = indicator_state(history)
    decision = 60
    long_signal = pd.Series(False, index=history.index)
    short_signal = pd.Series(False, index=history.index)
    short_signal.iloc[decision] = True
    trades = simulate_trades(history, state["atr14"], long_signal, short_signal, history.index[decision], history.index[80], {"stop_atr": 2.0, "target_atr": 3.0, "max_hold": 3}, "short", 7, "test")
    assert trades[0]["decision_date"] == str(history.index[decision].date())
    assert trades[0]["entry_date"] == str(history.index[decision + 1].date())
    assert trades[0]["entry"] == round(float(history["open"].iloc[decision + 1]), 6)
