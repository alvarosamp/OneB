import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.routers import asset_brief


@pytest.fixture
def client(monkeypatch):
    from app.main import app
    from app.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: object()
    idx = pd.date_range("2026-01-01", periods=300, freq="D")
    bars = pd.DataFrame({"open": 100.0, "high": 102.0, "low": 98.0, "close": 100.0}, index=idx)
    monkeypatch.setattr(asset_brief.market_data, "get_bars", lambda *a, **k: bars)
    monkeypatch.setattr(asset_brief.trend_router, "_reading", lambda asset: {"available": True})
    from app import response_cache
    response_cache.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_heatmap_has_cells_for_studied_assets(client):
    data = client.get("/api/analysis/hour-heatmap").json()
    assert set(data["assets"]) == {"NAS100", "SPX500", "XAUUSD", "EURUSD"}
    cell = data["assets"]["NAS100"]["cells"][0]
    assert {"weekday", "hour", "ratio", "cost_share"} <= set(cell)


def test_asset_brief_reports_atr_cost_and_evidence(client):
    data = client.get("/api/analysis/asset/nas100").json()
    assert data["key"] == "NAS100"
    assert data["market"]["atr_d1"] == pytest.approx(4.0)
    assert data["broker"]["symbol"] == "US100.s"
    assert len(data["hours_ahead"]) == 8
    assert any(e["test"] == "lab_v1" and e["status"] == "FAILED" for e in data["evidence"])
    assert "não é" in data["note"] or "não previsão" in data["note"]


def test_unknown_asset_is_404(client):
    assert client.get("/api/analysis/asset/BTCUSD").status_code == 404


def test_price_decimals_keep_fx_moves():
    from app.routers.api import price_decimals

    assert price_decimals(25000) == 2
    assert price_decimals(1.1203) == 5
    assert price_decimals(35.2) == 3


def test_next_session_lists_assets_and_events(client):
    data = client.get("/api/analysis/next-session").json()
    assert {a["key"] for a in data["assets"]} == {"NAS100", "SPX500", "XAUUSD", "EURUSD"}
    assert "events" in data and "não para onde" in data["note"]


def test_trade_plan_levels_and_measured_odds():
    from datetime import datetime, timezone

    from app.routers import asset_brief as ab

    now = datetime(2026, 10, 13, 14, 0, tzinfo=timezone.utc)
    plan = ab.trade_plan("XAUUSD", "short", 1.5, {"price": 4000.0, "atr_h1": 10.0}, {"expected_price": 50.0, "us_holiday": None}, [], now)
    assert plan["stop"] == 4015.0 and [t["price"] for t in plan["targets"]] == [3985.0, 3970.0, 3955.0]
    p = [t["p_target"] for t in plan["targets"]]
    assert p[0] > p[1] > p[2] > 0  # alvo mais longe = chance menor
    assert all(t["n"] > 1000 for t in plan["targets"])
    assert "não é sinal" in plan["note"]
    assert any("0,26" in w for w in plan["warnings"])  # vírgula decimal


def test_trade_plan_endpoint_validates_inputs(client):
    assert client.get("/api/analysis/trade-plan/XAUUSD?direction=up").status_code == 422
    assert client.get("/api/analysis/trade-plan/BTC").status_code == 404


def test_report_has_sections_and_shareable_text(client):
    data = client.get("/api/analysis/report/NAS100").json()
    titles = [s["title"] for s in data["sections"]]
    assert titles[:4] == ["Onde está o preço", "Quanto deve mexer", "Eventos", "Horário e custo"]
    assert "Se você comprar" in titles and "Se você vender" in titles
    assert data["text"].startswith("Análise OneB — Nasdaq 100") and "não é recomendação" in data["text"]


def test_hours_guide_is_digested_in_brasilia_time():
    from datetime import datetime, timezone

    from app.routers import asset_brief as ab

    summer = datetime(2026, 7, 15, 15, 0, tzinfo=timezone.utc)  # NY em EDT: Brasília = NY + 1
    d = ab.hours_digest("NAS100", summer)
    assert d["br_offset"] == 1
    assert any(b.startswith("Melhor janela para operar: 09h às 17h") for b in d["bullets"])
    assert any("ruído" in b for b in d["bullets"])
    winter = datetime(2026, 1, 15, 15, 0, tzinfo=timezone.utc)  # NY em EST: Brasília = NY + 2
    assert any(b.startswith("Melhor janela para operar: 10h às 18h") for b in ab.hours_digest("NAS100", winter)["bullets"])
    assert any("US100.s sai muito mais barato" in b for b in ab.hours_digest("SPX500", summer)["bullets"])


def test_hours_guide_endpoint(client):
    data = client.get("/api/analysis/hours-guide").json()
    assert set(data["assets"]) == {"NAS100", "SPX500", "XAUUSD", "EURUSD"}


def test_trade_plan_uses_user_mt5_entry_and_flags_basis_otherwise():
    from datetime import datetime, timezone

    from app.routers import asset_brief as ab

    now = datetime(2026, 10, 14, 14, 0, tzinfo=timezone.utc)
    m = {"price": 30574.5, "atr_h1": 80.0}
    chart = ab.trade_plan("NAS100", "long", 1.5, m, None, [], now)
    assert chart["entry_source"] == "chart" and chart["basis_note"]
    mine = ab.trade_plan("NAS100", "long", 1.5, m, None, [], now, entry=30897.85)
    assert mine["entry_source"] == "mt5" and mine["basis_note"] is None
    assert mine["stop"] == 30897.85 - 120 and mine["targets"][1]["price"] == 30897.85 + 240
    assert mine["stop_distance"] == chart["stop_distance"] == 120  # distância não depende da fonte do preço


def test_data_health_endpoint_reports_status(client):
    data = client.get("/api/analysis/data-health").json()
    assert data["status"] in ("ok", "warn", "fail")
    assert set(data["assets"]) == {"NAS100", "SPX500", "XAUUSD", "EURUSD"}
    assert "fake_fomc_rows" in data["calendar"]
    nas = data["assets"]["NAS100"]
    assert any(c["name"] == "diário" for c in nas["checks"]) and "futuro" in nas["source"]


def test_proof_page_payload(client):
    d = client.get("/api/analysis/proof").json()
    assert d["forecast_pass"] is True and {f["key"] for f in d["forecast"]} >= {"NAS100", "XAUUSD"}
    assert any(e["event"].startswith("CPI") and e["key"] == "NAS100" for e in d["events"])
    assert any(o["target_r"] == 2.0 and o["key"] == "XAUUSD" for o in d["odds"])
    assert any(r["tp1_r"] == 0.2 and r["win_rate"] > 0.7 and r["mean_r"] < 0 for r in d["promise_test"])
    assert len(d["not_promised"]) == 4


def test_proof_includes_replay(client):
    d = client.get("/api/analysis/proof").json()
    assert {r["rule"] for r in d["replay"]} == {"aleatorio", "acompanha_24h", "contra_1h"}
    assert d["replay_passed"] == []


def test_min_lot_balance():
    from datetime import datetime, timezone

    from app.routers.asset_brief import trade_plan

    p = trade_plan("XAUUSD", "long", 1.5, {"price": 2000.0, "atr_h1": 10.0}, None, [], datetime(2026, 10, 14, 15, tzinfo=timezone.utc))
    # stop 15 x 100 onças x 0,01 lote = US$ 15 -> 1% exige US$ 1.500
    assert p["min_lot"]["risk_usd"] == 15.0 and p["min_lot"]["balance_1pct"] == 1500


def test_proof_includes_plan_live(client, monkeypatch):
    from app.routers import asset_brief as ab

    monkeypatch.setattr(ab, "_m5", lambda key: None)  # sem rede: só o que estiver no banco
    d = client.get("/api/analysis/proof").json()
    assert "plan_live" in d and d["plan_live_start"] == "2026-10-15"


def test_sizing_table_flags_min_lot():
    from app.routers.asset_brief import sizing_table

    rows = sizing_table(1000.0, 1.0, 1.5, {"XAUUSD": {"atr_h1": 10.0}, "EURUSD": {"atr_h1": 0.001}, "NAS100": {}})
    gold = next(r for r in rows if r["key"] == "XAUUSD")
    # stop 15 x 100 onças x 0,01 = US$ 15 > US$ 10 de limite
    assert gold["below_minimum"] and gold["lots"] == 0 and round(gold["min_balance"]) == 1500
    eur = next(r for r in rows if r["key"] == "EURUSD")
    # stop 0,0015 x 100.000 = US$ 150 por lote -> US$ 10 cabem 0,06 lote
    assert not eur["below_minimum"] and abs(eur["lots"] - 0.06) < 1e-9
    assert rows[-1]["key"] == "NAS100" and rows[-1]["available"] is False
    assert rows[0]["key"] == "EURUSD"  # o que cabe com menos saldo vem primeiro


def test_sizing_endpoint_validates_input(client):
    assert client.get("/api/analysis/sizing?balance=0").status_code == 422
    assert client.get("/api/analysis/sizing?balance=1000&risk_pct=50").status_code == 422
    assert client.get("/api/analysis/sizing?balance=1000&stop_atr=3").status_code == 422
    d = client.get("/api/analysis/sizing?balance=1000&risk_pct=1").json()
    assert {r["key"] for r in d["rows"]} == set(asset_brief.ASSETS) and d["verified_at"] == asset_brief.BROKER_VERIFIED_AT


def test_plan_scoreboard_endpoint_records_live_plans(client, monkeypatch):
    """Ponta a ponta: barras de 5 min depois do início ao vivo -> planos gravados no banco e contados no placar.
    Banco em memória: o teste nunca toca planos reais do banco de desenvolvimento."""
    import numpy as np
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db import Base, get_db
    from app.main import app
    from app.models import PlanLiveRecord

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    idx = pd.date_range("2026-10-14 00:00", "2026-10-17 00:00", freq="5min", tz="UTC")
    rng = np.random.default_rng(3)
    px = 1000 + np.cumsum(rng.normal(0, 1, len(idx)))
    m5 = pd.DataFrame({"open": px, "high": px + 0.6, "low": px - 0.6, "close": px}, index=idx)
    monkeypatch.setattr(asset_brief, "_m5", lambda key: m5)
    try:
        # a leitura não grava nada
        assert client.get("/api/analysis/plan-scoreboard").json()["assets"]["NAS100"]["live"]["stored"] == 0
        # o job do agendador grava (record=True); depois a leitura mostra os gravados
        db = Session()
        asset_brief.plan_scoreboard("NAS100", m5, db, record=True)
        db.close()
        nas = client.get("/api/analysis/plan-scoreboard").json()["assets"]["NAS100"]
        # 'stored' conta só o gravado enquanto o plano estava aberto: depende do relógio, então só o limite
        assert 0 <= nas["live"]["stored"] <= 4
        assert nas["live"]["summary"]["long"]["plans"] == 2
        db = Session()
        assert db.query(PlanLiveRecord).filter(PlanLiveRecord.asset == "NAS100").count() == 4
        db.close()
        # segunda gravação não duplica
        db = Session()
        asset_brief.plan_scoreboard("NAS100", m5, db, record=True)
        assert db.query(PlanLiveRecord).filter(PlanLiveRecord.asset == "NAS100").count() == 4
        db.close()
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_daily_diary_joins_forecast_and_plans():
    from app.routers.asset_brief import daily_diary

    vol = {"NAS100": {"rows": [{"date": "2026-10-15", "expected_pct": 1.4, "low80_pct": 0.9, "high80_pct": 2.3, "realized_pct": 1.6,
                                "inside80": True, "event": False}]}}
    plans = {"NAS100": {"live": {"rows": [{"date": "2026-10-15", "direction": "long", "results": {"1": "hit", "2": "hit", "3": "open"}},
                                          {"date": "2026-10-16", "direction": "short", "results": {"1": "open", "2": "open", "3": "open"}}]}},
             "XAUUSD": {"live": None}}
    d = daily_diary(vol, plans)
    assert [x["date"] for x in d] == ["2026-10-16", "2026-10-15"]
    nas = d[1]["assets"][0]
    assert nas["range"]["inside80"] is True and nas["plans"]["long"]["2"] == "hit"


def test_sessions_from_hourly_splits_at_17h_new_york():
    """Pregão de 17:00 a 17:00 de NY: a sessão da noite (18:00) vira o pregão do dia seguinte e não apaga o de hoje."""
    from app.routers.asset_brief import sessions_from_hourly

    idx = pd.date_range("2026-10-13 22:00", "2026-10-15 23:00", freq="1h", tz="UTC")  # 18:00 ET de 13/10 até 19:00 ET de 15/10
    bars = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1}, index=idx)
    bars.loc["2026-10-15 15:00":"2026-10-15 15:00", ["high"]] = 130.0  # pico no meio do pregão de 15/10
    d = sessions_from_hourly(bars)
    assert list(d.index.strftime("%Y-%m-%d")) == ["2026-10-14", "2026-10-15", "2026-10-16"]
    assert d.loc["2026-10-15", "high"] == 130.0  # o pregão de 15/10 continua inteiro
    assert d.loc["2026-10-16", "high"] == 101.0  # a noite de 15/10 é o pregão de 16/10


def test_forecast_is_recorded_once_and_never_for_the_past():
    from datetime import datetime, timezone

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db import Base
    from app.routers.asset_brief import record_forecast, recorded_forecasts

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        # véspera, 20:00 UTC (16:00 de NY): antes do pregão de 16/10 começar (18:00 de NY de 15/10)
        record_forecast(db, "NAS100", "2026-10-16", "2026-10-15", 1.6, 1.0, 2.7, False, datetime(2026, 10, 15, 20, 0, tzinfo=timezone.utc))
        # nova tentativa com outro número: não reescreve
        record_forecast(db, "NAS100", "2026-10-16", "2026-10-15", 9.9, 9.0, 9.9, True, datetime(2026, 10, 16, 14, 0, tzinfo=timezone.utc))
        # pregão de 15/10 já terminou (17:00 de NY = 21:00 UTC): não grava previsão do passado
        record_forecast(db, "NAS100", "2026-10-15", "2026-10-14", 1.5, 1.0, 2.5, False, datetime(2026, 10, 15, 22, 0, tzinfo=timezone.utc))
        # gravada já durante o pregão de 17/10 (começou 18:00 de NY de 16/10)
        record_forecast(db, "NAS100", "2026-10-19", "2026-10-16", 1.4, 0.9, 2.3, False, datetime(2026, 10, 19, 14, 0, tzinfo=timezone.utc))
        saved = recorded_forecasts(db, "NAS100")
        assert set(saved) == {"2026-10-16", "2026-10-19"}
        assert saved["2026-10-16"]["expected_pct"] == 1.6 and saved["2026-10-16"]["before_session"] is True
        assert saved["2026-10-19"]["before_session"] is False
    finally:
        db.close()
        engine.dispose()
