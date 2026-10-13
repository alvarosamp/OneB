import numpy as np
import pandas as pd

from app import calendar_study as cs


def _m5(start="2024-03-01", days=40, seed=0, spike_at=None, spike=0.0):
    idx = pd.date_range(start, periods=days * 288, freq="5min", tz="UTC")
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.0005, len(idx))
    if spike_at is not None:
        for t in spike_at:
            r[idx.get_loc(t)] += spike
    close = 100 * np.exp(np.cumsum(r))
    return pd.DataFrame({"close": close, "spread": 0.01}, index=idx)


def test_price_at_uses_bar_ending_at_t():
    m5 = _m5(days=2)
    close, _ = cs.bar_end_series(m5)
    t = pd.Timestamp("2024-03-01 13:30", tz="UTC")
    assert close[t] == m5["close"].iloc[m5.index.get_loc(t - pd.Timedelta(minutes=5))]
    assert cs.log_ret(close, t, 0, 5) == np.log(m5["close"].loc[t] / m5["close"].loc[t - pd.Timedelta(minutes=5)])


def test_control_times_skip_weekends_and_event_days_and_keep_ny_clock():
    t0 = pd.Timestamp("2024-03-15 08:30").tz_localize(cs.NEW_YORK).tz_convert("UTC")
    ctrl = cs.control_times(t0, {pd.Timestamp("2024-03-14").date()}, n=3)
    local = [c.tz_convert(cs.NEW_YORK) for c in ctrl]
    assert [c.date().isoformat() for c in local] == ["2024-03-13", "2024-03-12", "2024-03-11"]
    assert all(c.strftime("%H:%M") == "08:30" for c in local)
    # 08/03 é antes da troca para horário de verão (10/03): mesmo 08:30 em NY, outro horário UTC
    before = cs.control_times(t0, set(), n=6)[-1]
    assert before.tz_convert(cs.NEW_YORK).strftime("%H:%M") == "08:30" and before.hour != ctrl[0].hour


def test_volatility_detects_spike_after_event():
    days = pd.bdate_range("2024-04-01", periods=30)
    events = [("CPI", pd.Timestamp(f"{d.date()} 08:30").tz_localize(cs.NEW_YORK).tz_convert("UTC")) for d in days[22:]]
    spikes = [t + pd.Timedelta(minutes=5) for _, t in events]
    m5 = _m5(start="2024-03-01", days=90, spike_at=[s - pd.Timedelta(minutes=5) for s in spikes], spike=0.01)
    close, _ = cs.bar_end_series(m5)
    out = cs.volatility(close, events * 2, {t.tz_convert(cs.NEW_YORK).date() for _, t in events})
    assert out["CPI"]["post5"]["median_ratio"] > 5 and out["CPI"]["post5"]["ci95"][0] > 1


def test_bh_controls_family():
    assert cs.bh({"a": 0.001, "b": 0.02, "c": 0.5}) == {"a": True, "b": True, "c": False}
    assert cs.bh({"a": 0.04, "b": 0.5}) == {"a": False, "b": False}
