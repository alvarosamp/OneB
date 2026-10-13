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
