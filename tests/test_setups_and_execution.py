import json

import numpy as np
import pandas as pd
import pytest

from app.baselines import PlainBreakout, ready_signals
from app.execution_sim import CostModel, replay_ready_signals, simulate_entry
from app.forward_stats import bootstrap_mean_ci, required_trades, summarize, verdict
from app.opportunity import SetupState
from app.setups import LOCK_PATH, PREREGISTRATION_DIR, PreregistrationError, load_preregistered
from app.setups.base import resample_bars
from app.setups.gold_fakeout import GoldFakeoutOpen

CONFIG = {
    "setup": "gold_fakeout_open", "symbol": "XAUUSD.s", "timeframe_minutes": 10, "trend_sma": 5,
    "break_lookback": 3, "session_window_brt": ["00:00", "23:59"], "server_utc_offset_hours": 0,
    "target_r": 1.5, "max_hold_minutes": 60,
}


def _bars(closes, start="2026-05-04 10:00", freq="10min", spread=20):
    idx = pd.date_range(start, periods=len(closes), freq=freq)
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame({
        "open": closes, "high": closes + 0.5, "low": closes - 0.5, "close": closes,
        "spread": spread, "tick_volume": 1,
    }, index=idx)


def test_breakout_with_two_confirmations_reaches_ready():
    bars = _bars([100, 100, 100, 100, 100, 100, 102, 103, 104])
    transitions = GoldFakeoutOpen(CONFIG).run(bars)
    states = [t.to_state for t in transitions]
    assert states[:2] == [SetupState.BREAK_DETECTED, SetupState.WAITING_CONFIRMATION_1]
    assert SetupState.WAITING_CONFIRMATION_2 in states and SetupState.READY_TO_ENTER in states
    ready = next(t for t in transitions if t.to_state == SetupState.READY_TO_ENTER)
    assert pd.Timestamp(ready.at) == bars.index[-1] + pd.Timedelta(minutes=10)
    assert ready.direction == "long"
    assert ready.payload["stop"] == pytest.approx(101.5)  # mínima da barra de rompimento


def test_fakeout_back_inside_level_invalidates():
    bars = _bars([100, 100, 100, 100, 100, 100, 102, 99.8, 100])
    transitions = GoldFakeoutOpen(CONFIG).run(bars)
    assert any(t.to_state == SetupState.INVALIDATED and "Fakeout" in t.reason for t in transitions)
    assert not any(t.to_state == SetupState.READY_TO_ENTER for t in transitions)


def test_state_machine_never_repaints():
    rng = np.random.default_rng(3)
    bars = _bars(100 + np.cumsum(rng.normal(0, 1, 400)))
    full = [t.to_dict() for t in GoldFakeoutOpen(CONFIG).run(bars)]
    for cut in (50, 137, 260, 399):
        prefix = [t.to_dict() for t in GoldFakeoutOpen(CONFIG).run(bars.iloc[:cut])]
        last = (bars.index[cut - 1] + pd.Timedelta(minutes=10)).isoformat()  # fechamento da última barra
        assert prefix == [t for t in full if t["at"] <= last]


def test_resample_drops_unclosed_bar():
    m5 = _bars([1, 2, 3, 4, 5], freq="5min")
    m10 = resample_bars(m5, 10, closed_before=m5.index[-1] + pd.Timedelta(minutes=4))
    assert len(m10) == 2  # a terceira barra M10 (só uma M5, ainda aberta) fica de fora


def test_long_entry_pays_ask_and_stop_gap_fills_at_worse_price():
    idx = pd.date_range("2026-05-04 10:00", periods=3, freq="5min")
    bars = pd.DataFrame({"open": [100, 100, 95], "high": [100.4, 100.2, 95.5], "low": [99.6, 99.5, 94.5],
                         "close": [100, 99.8, 95], "spread": [20, 20, 20], "tick_volume": 1}, index=idx)
    costs = CostModel(point=0.01, slippage=0.05, commission_roundtrip=0.1)
    trade = simulate_entry(bars, opportunity_id="x", direction="long", signal_at=idx[0] - pd.Timedelta(minutes=1),
                           stop=98.0, target_r=1.5, max_hold_minutes=60, costs=costs)
    assert trade.entry == pytest.approx(100.25)  # bid 100 + spread 0.20 + slippage 0.05
    assert trade.outcome == "STOP"
    assert trade.exit == pytest.approx(95 - 0.05)  # gap abaixo do stop: executa no preço observado
    assert trade.r < -1


def test_gap_in_position_is_censored_not_scored():
    idx = pd.DatetimeIndex(["2026-05-04 10:00", "2026-05-04 10:05", "2026-05-04 13:00"])
    bars = pd.DataFrame({"open": [100, 100, 100], "high": [100.1] * 3, "low": [99.9] * 3, "close": [100] * 3,
                         "spread": 10, "tick_volume": 1}, index=idx)
    trade = simulate_entry(bars, opportunity_id="x", direction="short", signal_at=idx[0] - pd.Timedelta(minutes=1),
                           stop=101, target_r=1.5, max_hold_minutes=240, costs=CostModel())
    assert trade.outcome == "CENSORED" and trade.r is None


def test_one_position_at_a_time():
    bars = _bars([100] * 40, freq="5min")
    signals = [
        {"opportunity_id": "a", "at": bars.index[0].isoformat(), "direction": "long", "stop": 99, "target_r": 1.5, "max_hold_minutes": 60},
        {"opportunity_id": "b", "at": bars.index[2].isoformat(), "direction": "long", "stop": 99, "target_r": 1.5, "max_hold_minutes": 60},
    ]
    trades, ignored = replay_ready_signals(bars, signals, CostModel())
    assert len(trades) == 1 and ignored[0]["reason"] == "position_already_open"


def test_plain_breakout_baseline_emits_ready_on_break_bar():
    bars = _bars([100, 100, 100, 100, 102])
    ready = ready_signals(PlainBreakout(CONFIG).run(bars))
    assert len(ready) == 1 and ready[0]["direction"] == "long"


def test_stats_and_preregistered_verdict():
    trades = [{"outcome": "TARGET", "r": 1.4, "mae_r": -0.2, "mfe_r": 1.5, "direction": "long", "entry_at": "2026-05-04T10:00", "brt_hour": 8}] * 30 + \
             [{"outcome": "STOP", "r": -1.0, "mae_r": -1.0, "mfe_r": 0.3, "direction": "short", "entry_at": "2026-05-05T10:00", "brt_hour": 9}] * 30
    summary = summarize(trades, sessions=40)
    assert summary["completed_trades"] == 60
    assert summary["expectancy_r"] == pytest.approx(0.2)
    rule = {"min_sessions": 250, "min_trades": 100}
    assert verdict(summary, rule)["status"] == "COLLECTING"
    assert verdict({**summary, "sessions": 300, "completed_trades": 120, "expectancy_ci95": [-0.1, 0.4]}, rule)["status"] == "ARCHIVE"
    assert verdict({**summary, "sessions": 300, "completed_trades": 120, "expectancy_ci95": [0.05, 0.4]}, rule, baseline_p95=0.1)["status"] == "PASSED"
    low, high = bootstrap_mean_ci([1.0, -1.0] * 50)
    assert low < 0 < high
    assert 400 < required_trades(0.15, 1.1) < 450


def test_preregistration_lock_detects_edits(tmp_path, monkeypatch):
    config, digest = load_preregistered("gold_fakeout_open_v1")
    assert config["prohibit_optimization"] is True and len(digest) == 64
    edited = tmp_path / "gold_fakeout_open_v1.json"
    edited.write_text(json.dumps({**config, "target_r": 2.0}), encoding="utf-8")
    monkeypatch.setattr("app.setups.PREREGISTRATION_DIR", tmp_path)
    monkeypatch.setattr("app.setups.LOCK_PATH", LOCK_PATH)
    with pytest.raises(PreregistrationError):
        load_preregistered("gold_fakeout_open_v1")
    assert PREREGISTRATION_DIR.exists()


def test_entry_never_happens_before_signal_bar_closes():
    m5 = _bars(list(100 + np.cumsum(np.random.default_rng(1).normal(0, 1, 3000))), freq="5min")
    m10 = resample_bars(m5, 10, closed_before=m5.index[-1] + pd.Timedelta(minutes=5))
    transitions = PlainBreakout(CONFIG).run(m10)
    ready = ready_signals(transitions)
    assert ready
    trades, _ = replay_ready_signals(m5, ready, CostModel())
    for trade in trades:
        signal_bar_open = pd.Timestamp(trade.signal_at) - pd.Timedelta(minutes=10)
        assert pd.Timestamp(trade.entry_at) >= signal_bar_open + pd.Timedelta(minutes=10)


def test_absolute_vendor_target_is_respected_and_crossed_target_skips():
    idx = pd.date_range("2026-05-04 10:00", periods=4, freq="5min")
    bars = pd.DataFrame({"open": [100, 100.5, 101, 102], "high": [100.6, 101.2, 102.5, 102.6], "low": [99.8, 100.2, 100.8, 101.5],
                         "close": [100.5, 101, 102, 102], "spread": 20, "tick_volume": 1}, index=idx)
    costs = CostModel(point=0.01, slippage=0.0, commission_roundtrip=0.0)
    trade = simulate_entry(bars, opportunity_id="v", direction="long", signal_at=idx[0], stop=99.0, target_r=None,
                           max_hold_minutes=60, costs=costs, target=102.0)
    assert trade.outcome == "TARGET" and trade.target == 102.0
    skipped = simulate_entry(bars, opportunity_id="v", direction="long", signal_at=idx[0], stop=99.0, target_r=None,
                             max_hold_minutes=60, costs=costs, target=100.1)
    assert skipped.outcome == "SKIPPED" and skipped.reason == "target_already_crossed"
