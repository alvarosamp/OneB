import numpy as np
import pandas as pd

from app import trend


def _frame(prices, start="2015-01-01"):
    idx = pd.bdate_range(start, periods=len(prices))
    return pd.DataFrame({"close": prices, "spread": np.full(len(prices), 0.0)}, index=idx)


def test_weight_uses_only_past_and_applies_next_day():
    n = 700
    prices = 100 * np.cumprod(np.full(n, 1.001))
    frame = _frame(prices)
    params = trend.TrendParams(financing_annual=0.0, slippage=0.0)
    out = trend.instrument_daily(frame, params)
    first_rebalance = trend.month_end_days(frame.index)[trend.month_end_days(frame.index) >= frame.index[params.min_history]][0]
    # No dia do rebalanceamento a posição ainda não existe; no seguinte, sim e comprada.
    assert np.isnan(out.loc[first_rebalance, "weight"])
    nxt = out.index[out.index > first_rebalance][0]
    assert out.loc[nxt, "weight"] > 0


def test_changing_the_future_does_not_change_past_weights():
    rng = np.random.default_rng(1)
    prices = 100 * np.cumprod(1 + rng.normal(0, 0.01, 900))
    params = trend.TrendParams()
    base = trend.instrument_daily(_frame(prices), params)["weight"]
    shocked = prices.copy()
    shocked[800:] *= 3
    after = trend.instrument_daily(_frame(shocked), params)["weight"]
    cut = _frame(prices).index[799]
    pd.testing.assert_series_equal(base[:cut], after[:cut])
    assert not base.equals(after)  # o choque no futuro muda o futuro, e só ele


def test_downtrend_goes_short_and_long_only_stays_long():
    prices = 100 * np.cumprod(np.full(700, 0.999))
    params = trend.TrendParams(financing_annual=0.0, slippage=0.0)
    assert (trend.instrument_daily(_frame(prices), params)["weight"].dropna() < 0).all()
    assert (trend.instrument_daily(_frame(prices), params, long_only=True)["weight"].dropna() > 0).all()


def test_costs_reduce_returns():
    rng = np.random.default_rng(2)
    prices = 100 * np.cumprod(1 + rng.normal(0, 0.01, 900))
    frame = _frame(prices)
    frame["spread"] = frame["close"] * 0.001
    free = trend.instrument_daily(frame, trend.TrendParams(financing_annual=0.0, slippage=0.0))["net"].sum()
    paid = trend.instrument_daily(frame, trend.TrendParams())["net"].sum()
    assert paid < free


def test_reading_flip_price_is_close_l_days_ago():
    prices = np.linspace(100, 200, 300)
    r = trend.reading(_frame(prices))
    h21 = next(h for h in r["horizons"] if h["days"] == 21)
    assert h21["flip_price"] == round(prices[-22], 6) and h21["direction"] == "alta"
    assert r["agreement"] == "todos em alta"


def test_verdict_rules():
    assert trend.verdict((0.001, 0.01), 0.002)["status"] == "PASSED"
    assert trend.verdict((0.001, 0.01), -0.001)["status"] == "DEGRADED"
    assert trend.verdict((-0.001, 0.01), 0.002)["status"] == "NOT_SIGNIFICANT"
    assert trend.verdict((-0.01, -0.001), 0.002)["status"] == "FAILED"


def test_block_bootstrap_ci_contains_mean():
    v = np.random.default_rng(3).normal(0.01, 0.02, 120)
    lo, hi = trend.ci(v, resamples=2000)
    assert lo < v.mean() < hi
