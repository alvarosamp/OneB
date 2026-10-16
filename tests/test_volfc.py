import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from app import volfc


def test_trading_day_rolls_at_17h_new_york():
    # 16:55 e 17:05 de NY (EDT = UTC-4) caem em pregões diferentes.
    idx = pd.date_range("2024-07-01 00:00", "2024-07-03 23:55", freq="5min", tz="UTC")
    m5 = pd.DataFrame({"high": 101.0, "low": 99.0, "close": 100.0}, index=idx)
    days = volfc.trading_days(m5)
    assert list(days.index.strftime("%Y-%m-%d"))[:2] == ["2024-07-02", "2024-07-03"]
    assert days["range"].iloc[0] == 0.02


def test_har_fit_recovers_coefficients():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(500, 3))
    y = 0.5 + X @ np.array([0.2, 0.5, 0.1]) + rng.normal(scale=0.01, size=500)
    coef = volfc.fit_ols(X, y)
    assert np.allclose(coef, [0.5, 0.2, 0.5, 0.1], atol=0.01)


def test_result_passed_and_app_model_is_complete():
    r = json.loads((Path(__file__).resolve().parents[1] / "app" / "research_results" / "volfc_v1.json").read_text(encoding="utf-8"))
    assert r["status"] == "PASSED" and r["event_kinds"] == ["CPI", "FOMC", "NFP"]
    for model in r["app_model"].values():
        assert len(model["coef"]) == 5 and model["q10"] < 0 < model["q90"]
        assert 0.75 <= model["coverage80_test"] <= 0.85


def test_forecast_skips_open_session_and_flags_event(monkeypatch):
    from app.routers import asset_brief

    class E:
        def __init__(self, name, when):
            self.event_name, self.event_date = name, when

    class Q:
        def __init__(self, rows):
            self.rows = rows

        def filter(self, *a):
            return self

        def all(self):
            return self.rows

    class DB:
        def query(self, *_):
            return Q([E("CPI m/m", pd.Timestamp("2026-10-15 12:30", tz="UTC"))])

    idx = pd.bdate_range("2026-05-01", "2026-10-14")
    daily = pd.DataFrame({"high": 101.0, "low": 99.0, "close": 100.0}, index=idx)
    now = datetime(2026, 10, 14, 15, 0, tzinfo=timezone.utc)  # 11:00 em NY: pregão de 14/10 ainda aberto
    fc = asset_brief.range_forecast("NAS100", daily, DB(), now)
    assert fc["based_on"] == "2026-10-13" and fc["target_date"] == "2026-10-14"
    assert fc["event"] is None  # o CPI é no dia 15
    now = datetime(2026, 10, 14, 22, 0, tzinfo=timezone.utc)  # 18:00 em NY: pregão de 14/10 fechado
    fc = asset_brief.range_forecast("NAS100", daily, DB(), now)
    assert fc["target_date"] == "2026-10-15" and fc["event"] == "CPI m/m"
    assert fc["low80_pct"] < fc["expected_pct"] < fc["high80_pct"]


def test_scoreboard_uses_only_previous_day_and_counts_coverage():
    from app.routers import asset_brief

    class Q:
        def filter(self, *a):
            return self

        def all(self):
            return []

    class DB:
        def query(self, *_):
            return Q()

    idx = pd.bdate_range("2026-06-01", "2026-10-16")
    rng = np.random.default_rng(3)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx))))
    daily = pd.DataFrame({"high": close * 1.01, "low": close * 0.99, "close": close}, index=idx)
    now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
    sb = asset_brief.volfc_scoreboard("NAS100", daily, DB(), now)
    assert [r["date"] for r in sb["rows"]] == ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"]
    assert sb["summary"]["days"] == 5 and 0 <= sb["summary"]["inside80"] <= 5
    json.dumps(sb)  # tipos nativos: a API serializa sem erro
    # mudar o dia 16 não pode alterar a previsão do dia 16 (só a véspera conta)
    before = sb["rows"][-1]["expected_pct"]
    daily.loc[idx[-1], "high"] *= 1.5
    assert asset_brief.volfc_scoreboard("NAS100", daily, DB(), now)["rows"][-1]["expected_pct"] == before


def test_us_holiday_flag():
    from app.routers import asset_brief

    assert asset_brief.us_holiday(pd.Timestamp("2026-10-12")) == "Columbus Day"
    assert asset_brief.us_holiday(pd.Timestamp("2026-10-13")) is None
