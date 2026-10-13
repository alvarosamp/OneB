from types import SimpleNamespace

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.main import app
from app.routers import trend as trend_router


def test_readings_without_test_result_are_descriptive(monkeypatch, tmp_path):
    idx = pd.bdate_range("2024-01-01", periods=400)
    bars = pd.DataFrame({"close": np.linspace(100, 140, 400)}, index=idx)
    monkeypatch.setattr(trend_router.market_data, "get_bars", lambda *a, **k: bars)
    monkeypatch.setattr(trend_router, "RESULT_PATH", tmp_path / "nao_existe.json")
    trend_router.response_cache.clear()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    try:
        body = TestClient(app).get("/api/trend/readings").json()
    finally:
        app.dependency_overrides.clear()
    assert body["evidence"]["status"] == "PENDING" and body["evidence"]["as_evidence"] is False
    first = body["assets"][0]
    assert first["available"] and first["agreement"] == "todos em alta"
    assert [h["days"] for h in first["horizons"]] == [21, 63, 252]
