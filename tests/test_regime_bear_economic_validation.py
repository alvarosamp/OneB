import pandas as pd

from scripts.regime_bear_economic_validation import simulate_top_quantile


def test_economic_simulation_charges_turnover_and_uses_non_overlapping_dates():
    rows = []
    for date in pd.date_range("2025-01-02", periods=6, freq="B"):
        for number in range(10):
            rows.append({"date": date, "symbol": f"S{number}", "volatility_atr": number, "fwd_return_5d": float(number - 4)})
    report = simulate_top_quantile(pd.DataFrame(rows), round_trip_cost_bps=20)
    assert len(report["periods"]) == 2
    assert report["periods"][0]["cost_bps"] > 0
    assert report["summary"]["max_drawdown_pct"] is not None
    assert report["summary"]["sample_adequate"] is False
    assert report["summary"]["annualized_return_approx_pct"] is None
