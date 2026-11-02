import numpy as np
import pandas as pd

from app.research import lab


def _ohlcv(opens):
    idx = pd.bdate_range("2024-01-01", periods=len(opens))
    o = pd.Series(opens, index=idx, dtype=float)
    return pd.DataFrame({"open": o, "high": o, "low": o, "close": o, "volume": 1.0})


def test_execution_is_next_open_no_lookahead():
    df = _ohlcv([100, 100, 110, 121, 121, 121])
    pos = pd.Series([0, 1, 0, 0, 0, 0], index=df.index, dtype=float)  # sinal no fechamento do dia 1
    ret = lab.strategy_returns(pos, df, cost=0)
    # entra na abertura do dia 2 (110), sai na abertura do dia 3 (121): +10%
    assert round(ret.sum(), 6) == 0.1
    assert ret.iloc[0] == 0 and ret.iloc[1] == 0


def test_cost_charged_on_entry_and_exit():
    df = _ohlcv([100] * 8)
    pos = pd.Series([0, 1, 1, 0, 0, 0, 0, 0], index=df.index, dtype=float)
    ret = lab.strategy_returns(pos, df, cost=0.001)
    assert round(ret.sum(), 6) == -0.002


def test_simulate_position_trailing_stop_and_max_hold():
    close = np.array([10, 10, 11, 12, 11, 9, 9, 9], dtype=float)
    entry = np.array([0, 1, 0, 0, 0, 0, 0, 0], dtype=bool)
    atr = np.full(8, 0.5)
    pos = lab.simulate_position(entry, None, close, atr=atr, trail_mult=2)
    assert pos.tolist() == [0, 1, 1, 1, 0, 0, 0, 0]  # 11 <= 12 - 2*0.5 sai
    pos2 = lab.simulate_position(entry, None, close, max_hold=2)
    assert pos2.tolist() == [0, 1, 1, 0, 0, 0, 0, 0]


def test_trade_returns_and_metrics():
    df = _ohlcv([100, 100, 110, 121, 121, 121, 121, 133.1, 133.1])
    pos = pd.Series([0, 1, 1, 0, 0, 1, 0, 0, 0], index=df.index, dtype=float)
    ret = lab.strategy_returns(pos, df, cost=0)
    trades = lab.trade_returns(pos, ret)
    assert len(trades) == 2 and round(trades[0], 4) == 0.1 and round(trades[1], 4) == 0.1
    m = lab.metrics(pd.concat([ret] * 5, ignore_index=True), trades)
    assert m["trades"] == 2 and m["win_rate_pct"] == 100.0
