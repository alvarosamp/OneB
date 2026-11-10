from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from app import regime_engine
from app.regime_engine import (
    LocalRegime,
    _period_change,
    macro_correlation_analysis,
    macro_correlation_window,
    macro_lead_lag_candidates,
    macro_relationship_dynamics,
    trend_analysis,
)


def _history(*, rising: bool = True) -> pd.DataFrame:
    index = pd.bdate_range("2026-01-01", periods=100, tz="UTC")
    direction = 1 if rising else -1
    close = pd.Series(100 + direction * np.arange(100) * 0.4, index=index)
    return pd.DataFrame(
        {
            "open": close - direction * 0.1,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 1_000,
        },
        index=index,
    )


def _history_from_returns(returns: np.ndarray, *, hour: int = 0) -> pd.DataFrame:
    close = 100 * np.cumprod(np.concatenate(([1.0], 1 + returns)))
    index = pd.bdate_range("2025-01-01", periods=len(close), tz="UTC") + pd.Timedelta(hours=hour)
    return pd.DataFrame({"close": close}, index=index)


def test_trend_analysis_reports_price_changes_as_percent():
    result = trend_analysis(_history())
    assert result is not None
    assert result["direction"] in {"ALTA", "ALTA FORTE"}
    assert result["change_unit"] == "%"
    assert result["change_5d"] == 1.45
    assert result["change_20d"] == 6.08
    assert result["change_60d"] == 20.76
    assert result["last"] == 139.6
    assert result["as_of"] == "2026-05-20T00:00:00+00:00"
    assert result["age_days"] >= 0


def test_trend_analysis_reports_yield_changes_as_basis_points():
    history = _history()
    history[["open", "high", "low", "close"]] /= 25
    result = trend_analysis(history, yield_series=True)
    assert result is not None
    assert result["change_unit"] == "bps"
    assert result["change_5d"] == 8.0
    assert result["change_20d"] == 32.0
    assert result["change_60d"] == 96.0


def test_trend_analysis_reports_falling_market_with_negative_changes():
    result = trend_analysis(_history(rising=False))

    assert result is not None
    assert result["direction"] in {"BAIXA", "BAIXA FORTE"}
    assert result["change_5d"] == -3.21
    assert result["change_20d"] == -11.7
    assert result["change_60d"] == -28.44


def test_trend_analysis_is_independent_of_input_row_order():
    ordered = trend_analysis(_history())
    shuffled = trend_analysis(_history().sample(frac=1, random_state=7))

    assert shuffled == ordered


@pytest.mark.parametrize(
    ("adx_value", "expected"),
    [(17.9, "FRACA"), (18.0, "MODERADA"), (24.9, "MODERADA"), (25.0, "FORTE"), (np.nan, "INDEFINIDA")],
)
def test_trend_analysis_strength_thresholds(monkeypatch, adx_value, expected):
    monkeypatch.setattr(
        regime_engine,
        "local_regime",
        lambda _history: LocalRegime(label="NEUTRAL", score=0.0, factors=[]),
    )
    monkeypatch.setattr(
        regime_engine.indicators,
        "adx",
        lambda *_args, **_kwargs: pd.DataFrame({"adx": [adx_value]}, index=[_history().index[-1]]),
    )

    result = trend_analysis(_history())

    assert result is not None
    assert result["strength"] == expected
    expected_adx = None if np.isnan(adx_value) else adx_value
    assert result["adx14"] == expected_adx


def test_period_change_returns_none_when_reference_price_is_zero():
    close = pd.Series([0.0, 10.0])

    assert _period_change(close, 1, yield_series=False) is None
    assert _period_change(close, 2, yield_series=False) is None


def test_macro_correlation_matrix_aligns_session_dates_and_finds_inverse_relationships():
    pattern = np.tile(np.array([0.01, -0.005, 0.008, -0.004]), 20)
    histories = {
        "NASDAQ": _history_from_returns(pattern),
        "SP500": _history_from_returns(pattern * 0.5, hour=4),
        "DXY": _history_from_returns(-pattern, hour=2),
    }

    result = macro_correlation_window(histories, keys=("NASDAQ", "SP500", "DXY"), sessions=60)
    matrix = {row["key"]: row["values"] for row in result["matrix"]}

    assert matrix["NASDAQ"]["NASDAQ"] == 1.0
    assert matrix["NASDAQ"]["SP500"] == 1.0
    assert matrix["NASDAQ"]["DXY"] == -1.0
    assert result["strongest_positive"][0]["observations"] == 60
    assert result["strongest_negative"][0]["correlation"] == -1.0


def test_macro_correlation_uses_yield_changes_instead_of_yield_levels():
    pattern = np.tile(np.array([0.01, -0.005, 0.008, -0.004]), 20)
    yield_close = 4 + np.concatenate(([0.0], np.cumsum(pattern)))
    yield_history = pd.DataFrame(
        {"close": yield_close},
        index=pd.bdate_range("2025-01-01", periods=len(yield_close), tz="UTC"),
    )
    histories = {"US10Y": yield_history, "GOLD": _history_from_returns(-pattern)}

    result = macro_correlation_window(histories, keys=("US10Y", "GOLD"), sessions=60)
    matrix = {row["key"]: row["values"] for row in result["matrix"]}

    assert matrix["US10Y"]["GOLD"] == -1.0


def test_macro_correlation_marks_pairs_without_enough_common_history_as_missing():
    short = _history_from_returns(np.array([0.01, -0.01, 0.005]))

    result = macro_correlation_window({"NASDAQ": short, "GOLD": short}, keys=("NASDAQ", "GOLD"), sessions=20)
    matrix = {row["key"]: row["values"] for row in result["matrix"]}

    assert matrix["NASDAQ"]["NASDAQ"] is None
    assert matrix["NASDAQ"]["GOLD"] is None
    assert result["strongest_positive"] == []
    assert result["strongest_negative"] == []


def test_macro_correlation_analysis_includes_quarter_semester_and_year():
    pattern = np.tile(np.array([0.01, -0.005, 0.008, -0.004]), 66)
    histories = {
        "NASDAQ": _history_from_returns(pattern),
        "GOLD": _history_from_returns(-pattern),
    }

    result = macro_correlation_analysis(histories)

    assert {"20", "60", "3m", "6m", "12m"} <= set(result)
    for window, sessions in (("3m", 63), ("6m", 126), ("12m", 252)):
        pair = next(row for row in result[window]["strongest_negative"] if row["left"] == "GOLD" and row["right"] == "NASDAQ")
        assert pair["observations"] == sessions
        assert pair["correlation"] == -1.0


def test_macro_correlation_excludes_unfinished_current_session(monkeypatch):
    monkeypatch.setattr(regime_engine, "_last_completed_market_date", lambda: date(2026, 9, 24))
    history = pd.DataFrame(
        {"close": [100.0, 101.0, 150.0]},
        index=pd.DatetimeIndex(["2026-09-23", "2026-09-24", "2026-09-25"], tz="UTC"),
    )

    changes = regime_engine._daily_change_series(history, yield_series=False)

    assert len(changes) == 1
    assert changes.index[-1].date() == date(2026, 9, 24)
    assert changes.iloc[-1] == pytest.approx(0.01)


def test_relationship_dynamics_detects_sign_reversal_and_strength_change():
    keys = ("NASDAQ", "DXY", "GOLD")
    windows = {
        "20": {
            "matrix": [
                {"key": "NASDAQ", "values": {"NASDAQ": 1.0, "DXY": -0.7, "GOLD": 0.8}},
                {"key": "DXY", "values": {"NASDAQ": -0.7, "DXY": 1.0, "GOLD": -0.1}},
                {"key": "GOLD", "values": {"NASDAQ": 0.8, "DXY": -0.1, "GOLD": 1.0}},
            ]
        },
        "60": {
            "matrix": [
                {"key": "NASDAQ", "values": {"NASDAQ": 1.0, "DXY": 0.4, "GOLD": 0.3}},
                {"key": "DXY", "values": {"NASDAQ": 0.4, "DXY": 1.0, "GOLD": -0.6}},
                {"key": "GOLD", "values": {"NASDAQ": 0.3, "DXY": -0.6, "GOLD": 1.0}},
            ]
        },
    }

    rows = macro_relationship_dynamics(windows)
    by_pair = {(row["left"], row["right"]): row for row in rows}

    assert set(keys) == {"NASDAQ", "DXY", "GOLD"}
    assert by_pair[("NASDAQ", "DXY")]["status"] == "INVERSAO"
    assert by_pair[("NASDAQ", "GOLD")]["status"] == "FORTALECENDO"
    assert by_pair[("DXY", "GOLD")]["status"] == "ENFRAQUECENDO"


def test_lead_lag_scan_finds_known_two_session_leader():
    rng = np.random.default_rng(42)
    leader_returns = rng.normal(0, 0.01, 100)
    follower_returns = np.concatenate((np.zeros(2), leader_returns[:-2]))
    histories = {
        "NASDAQ": _history_from_returns(leader_returns),
        "GOLD": _history_from_returns(follower_returns),
    }

    rows = macro_lead_lag_candidates(histories, keys=("NASDAQ", "GOLD"), sessions=60, max_lag=3)

    assert len(rows) == 1
    assert rows[0]["leader"] == "NASDAQ"
    assert rows[0]["follower"] == "GOLD"
    assert rows[0]["lag_sessions"] == 2
    assert rows[0]["correlation"] == 1.0
    assert rows[0]["improvement"] >= 0.75


def test_lead_lag_scan_does_not_relabel_contemporaneous_correlation_as_leadership():
    rng = np.random.default_rng(7)
    returns = rng.normal(0, 0.01, 100)
    histories = {"NASDAQ": _history_from_returns(returns), "SP500": _history_from_returns(returns)}

    assert macro_lead_lag_candidates(histories, keys=("NASDAQ", "SP500"), sessions=60) == []


def test_trend_analysis_handles_insufficient_history():
    assert trend_analysis(pd.DataFrame()) is None
    assert trend_analysis(_history().tail(20)) is None
    assert trend_analysis(_history().tail(54)) is None
