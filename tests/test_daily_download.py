import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("daily", ROOT / "scripts" / "download_dukascopy_daily.py")
daily = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daily)


def _side(days, offset):
    ts = [int(pd.Timestamp(d, tz="UTC").timestamp() * 1000) for d in days]
    return pd.DataFrame({"timestamp": ts, "open": 100 + offset, "high": 101 + offset, "low": 99 + offset, "close": 100 + offset})


def test_fill_missing_ask_year_from_bid_with_median_spread():
    y2020 = pd.bdate_range("2020-01-01", "2020-12-31")
    y2021 = pd.bdate_range("2021-01-01", "2021-12-31")
    bid = _side(list(y2020) + list(y2021), 0.0)
    ask = _side(list(y2020), 0.5)
    filled, spread = daily.fill_side(ask, bid, [2021], +1)
    assert spread == 0.5
    assert len(filled) == len(bid)
    assert (filled["close"].iloc[-1] - bid["close"].iloc[-1]) == 0.5


def test_trading_bars_drop_weekends_and_flat_bars():
    days = pd.date_range("2024-01-05", periods=4)  # sex, sáb, dom, seg
    f = _side(days, 0.0)
    f.loc[3, ["high", "low"]] = 100.0  # segunda plana
    assert len(daily.trading_bars(f)) == 1


def test_daily_from_hourly_uses_utc_day_and_skips_flat_hours():
    hours = pd.date_range("2024-01-08 00:00", periods=48, freq="h", tz="UTC")  # segunda e terça
    ts = (hours - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(milliseconds=1)
    base = [float(x) for x in range(48)]
    f = pd.DataFrame({"timestamp": ts, "open": base, "high": [x + 1 for x in base], "low": [x - 1 for x in base], "close": [x + 0.5 for x in base]})
    f.loc[47, ["open", "high", "low", "close"]] = 46.5  # última hora plana (preenchimento)
    d = daily.daily_from_hourly(f)
    assert len(d) == 2
    assert d.loc[0, "open"] == 0 and d.loc[0, "close"] == 23.5 and d.loc[0, "high"] == 24
    assert d.loc[1, "close"] == 46.5 and d.loc[1, "timestamp"] == int(pd.Timestamp("2024-01-09", tz="UTC").timestamp() * 1000)


def test_covers_accepts_holidays_but_not_a_missing_month():
    days = [d for d in pd.bdate_range("2017-01-01", "2017-12-31") if d not in (pd.Timestamp("2017-07-04"), pd.Timestamp("2017-12-25"))]
    full = _side(days, 0.0)
    assert daily.covers(full, "2017-01-01", "2018-01-01")
    no_feb = _side([d for d in days if d.month != 2], 0.0)
    assert not daily.covers(no_feb, "2017-01-01", "2018-01-01")
    first_half = _side([d for d in days if d.month <= 6], 0.0)
    assert not daily.covers(first_half, "2017-01-01", "2018-01-01")
