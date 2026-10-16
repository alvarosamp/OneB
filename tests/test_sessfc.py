from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from app import sessfc


def _bars(start: str, end: str, seed: int = 1) -> pd.DataFrame:
    idx = pd.date_range(start, end, freq="5min", tz="UTC")
    idx = idx[idx.dayofweek < 5]
    rng = np.random.default_rng(seed)
    px = 1000 + np.cumsum(rng.normal(0, 1, len(idx)))
    return pd.DataFrame({"open": px, "high": px + 0.5, "low": px - 0.5, "close": px}, index=idx)


def test_window_follows_new_york_close_across_dst():
    # verão: 16:00 de NY = 20:00 UTC; inverno: 21:00 UTC. Entrada sempre 13:30 UTC (10:30 de Brasília)
    _, entry, close = sessfc.window_bounds(date(2026, 10, 15))
    assert entry == pd.Timestamp("2026-10-15 13:30", tz="UTC") and close == pd.Timestamp("2026-10-15 20:00", tz="UTC")
    _, _, close_w = sessfc.window_bounds(date(2026, 11, 16))
    assert close_w == pd.Timestamp("2026-11-16 21:00", tz="UTC")
    pre, _, _ = sessfc.window_bounds(date(2026, 10, 15))
    assert pre == pd.Timestamp("2026-10-14 22:00", tz="UTC")  # 18:00 de NY da véspera


def test_windows_and_features_use_only_the_past():
    m5 = _bars("2026-08-03", "2026-10-16 23:55")
    win = sessfc.windows(m5)
    assert len(win) > 40 and (win["bars"] >= sessfc.MIN_BARS).all()
    day = win.index[30]
    entry, close = sessfc.window_bounds(day.date())[1:]
    seg = m5[(m5.index >= entry) & (m5.index < close)]
    assert abs(win.loc[day, "range"] - (seg["high"].max() - seg["low"].min()) / seg["open"].iloc[0]) < 1e-12
    f = sessfc.features(win, {day.date()})
    lr = np.log(win["range"])
    assert abs(f.loc[day, "d"] - lr.iloc[29]) < 1e-12  # véspera, nunca o próprio dia
    assert abs(f.loc[day, "m"] - lr.iloc[8:30].mean()) < 1e-12
    assert f.loc[day, "event"] == 1.0 and f.loc[win.index[31], "event"] == 0.0


def test_forecast_today_needs_entry_bar_and_reports_points():
    m5 = _bars("2026-08-03", "2026-10-15 15:00")
    model = {"coef": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0], "q10": -0.3, "q90": 0.3}  # = média de 22 dias
    before = sessfc.forecast_today(m5, model, set(), datetime(2026, 10, 15, 13, 0, tzinfo=timezone.utc))
    assert before is None  # antes das 13:30 UTC não há previsão
    fc = sessfc.forecast_today(m5, model, set(), datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc))
    hist = sessfc.windows(m5[m5.index < pd.Timestamp("2026-10-15 13:30", tz="UTC")])
    expected = float(np.exp(np.log(hist["range"]).iloc[-22:].mean()) * 100)
    assert abs(fc["expected_pct"] - expected) < 1e-9 and fc["low80_pct"] < fc["expected_pct"] < fc["high80_pct"]
    assert abs(fc["expected_points"] - fc["expected_pct"] / 100 * fc["entry_price"]) < 1e-9
    assert fc["closed"] is False and fc["so_far_pct"] > 0


def test_session_forecast_only_for_approved_asset_and_is_recorded(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db import Base
    from app.routers import asset_brief

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    result = {"generated_at": "2026-10-14T00:00:00+00:00",
              "app_model": {"NAS100": {"coef": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0], "q10": -0.3, "q90": 0.3}}}
    monkeypatch.setattr(asset_brief, "_result", lambda name: result if name == "sessfc_v1.json" else None)
    m5 = _bars("2026-08-03", "2026-10-15 15:00")
    now = datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc)
    try:
        assert asset_brief.session_forecast("XAUUSD", db, now, m5=m5) is None  # não aprovado: não aparece
        fc = asset_brief.session_forecast("NAS100", db, now, m5=m5)
        assert fc["test"] == "sessfc_v1" and asset_brief.recorded_forecasts(db, "NAS100", kind="sessfc") == {}  # leitura não grava
        asset_brief.session_forecast("NAS100", db, now, m5=m5, record=True)  # o job grava
        saved = asset_brief.recorded_forecasts(db, "NAS100", kind="sessfc")
        assert saved["2026-10-15"]["expected_pct"] == fc["expected_pct"]
        # o placar começa no dia útil seguinte à geração do teste (15/10) e usa o gravado
        full = _bars("2026-08-03", "2026-10-16 23:55")
        board = asset_brief.sessfc_scoreboard("NAS100", db, full)
        assert board["start"] == "2026-10-15" and board["rows"][0]["date"] == "2026-10-15"
        assert board["rows"][0]["registered"] == "gravada" and abs(board["rows"][0]["expected_pct"] - fc["expected_pct"]) < 1e-9
    finally:
        db.close()
        engine.dispose()


def test_trade_plan_warns_when_target_is_beyond_rest_of_day():
    from app.routers.asset_brief import trade_plan

    now = datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc)
    sfc = {"closed": False, "high80_points": 250.0}
    p = trade_plan("NAS100", "long", 1.5, {"price": 30000.0, "atr_h1": 100.0}, None, [], now, session_fc=sfc)
    # stop 150: TP1 = 150 cabe; TP2 = 300 passa de 250
    assert any(w.startswith("TP2 fica além do que o mercado anda até o fechamento") for w in p["warnings"])
    assert not any("até o fechamento" in w for w in trade_plan("NAS100", "long", 1.5, {"price": 30000.0, "atr_h1": 100.0}, None, [], now)["warnings"])
