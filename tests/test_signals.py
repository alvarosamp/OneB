from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from app import signal_eval as se

REFS = {"XAUUSD": 4180.0, "NAS100": 29700.0, "SPX500": 7690.0, "EURUSD": 1.12}


@pytest.mark.parametrize("text,expected", [
    ("XAUUSD BUY 4180 SL 4170 TP1 4185 TP2 4190 TP3 4200", ("XAUUSD", "long", 4180.0, 4170.0, [4185.0, 4190.0, 4200.0])),
    ("🟢 OURO - COMPRA\nEntrada: 4.180,50\nStop: 4.170\nAlvo 1: 4.185\nAlvo 2: 4.190", ("XAUUSD", "long", 4180.5, 4170.0, [4185.0, 4190.0])),
    ("Nasdaq venda 29700 stop 29800 alvos 29650 / 29600 / 29500", ("NAS100", "short", 29700.0, 29800.0, [29650.0, 29600.0, 29500.0])),
    ("SELL US100 @ 29,700 - 29,720 SL 29,800 TP 29,650 TP 29,550", ("NAS100", "short", 29710.0, 29800.0, [29650.0, 29550.0])),
    ("XAU/USD SELL NOW 4185\nTP 4180\nTP 4175\nSL 4195", ("XAUUSD", "short", 4185.0, 4195.0, [4180.0, 4175.0])),
    ("EURUSD compra entrada 1.1210 stop 1.1190 tp1 1.1230 tp2 1.1260", ("EURUSD", "long", 1.121, 1.119, [1.123, 1.126])),
])
def test_parse_signal_formats(text, expected):
    s = se.parse_signal(text, REFS)
    assert (s["asset"], s["direction"], s["entry"], s["stop"], s["targets"]) == expected


@pytest.mark.parametrize("text,msg", [
    ("compra ouro 4180 stop 4190 alvo 4200", "lado errado"),
    ("ouro compra 4180 alvo 4200", "stop"),
    ("ouro 4180 stop 4170 alvo 4200", "compra ou de venda"),
    ("bitcoin compra 60000 stop 59000 alvo 62000", "ativo"),
])
def test_parse_signal_errors(text, msg):
    assert msg in se.parse_signal(text, REFS)["error"]


def _walk(n_days: int = 40, seed: int = 3, drift: float = 0.0) -> pd.DataFrame:
    idx = pd.date_range("2026-08-03", periods=n_days * 288, freq="5min", tz="UTC")
    idx = idx[idx.dayofweek < 5]
    rng = np.random.default_rng(seed)
    px = 1000 + np.cumsum(rng.normal(drift, 1, len(idx)))
    return pd.DataFrame({"open": px, "high": px + 0.2, "low": px - 0.2, "close": px}, index=idx)


def test_base_rates_match_random_walk_and_neutral_removes_drift():
    m5 = _walk()
    r = se.base_rates(m5, "long", 1.0, [1.0, 2.0], spread=0.0)
    p1, p2 = (t["p_target"] for t in r["targets"])
    assert 0.40 < p1 < 0.60 and 0.20 < p2 < 0.42  # passeio aleatório: ~1/(1+R), menos os que vencem em 24 h
    trend = _walk(drift=0.05)
    up = se.base_rates(trend, "long", 1.0, [1.0], 0.0)["targets"][0]
    down = se.base_rates(trend, "short", 1.0, [1.0], 0.0)["targets"][0]
    assert up["p_target"] > down["p_target"]  # com tendência, a compra "acerta" mais...
    n = se.neutral(up, down)
    assert down["p_target"] < n["p_target"] < up["p_target"] and n["n"] == up["n"] + down["n"]  # ...a neutra tira isso


def test_resolve_signal_uses_signal_distances_from_entry_bar():
    idx = pd.date_range("2026-10-15 13:00", periods=400, freq="5min", tz="UTC").as_unit("s")  # como vem do Yahoo
    px = np.r_[[100.0] * 3, [104.5] * 2, [96.0] * 395]  # sobe 4,5 e depois cai 4
    m5 = pd.DataFrame({"open": px, "high": px, "low": px, "close": px}, index=idx)
    created = datetime(2026, 10, 15, 13, 2, 7, 123456, tzinfo=timezone.utc)  # com microssegundos, como o banco grava
    out = se.resolve_signal(m5, created, "long", 3.0, [4.0, 6.0], spread=0.0)
    # entrada na barra das 13:05 (100); alvo de 4 bate em 104,5; alvo de 6 não, e depois o stop de 3 (97) bate
    assert out["results"] == ["hit", "stop"] and out["result_r"][0] == pytest.approx(4 / 3) and out["result_r"][1] == -1.0


def test_scoreboard_compares_observed_with_expected():
    from app.routers.signals import scoreboard

    rows = [{"source": "VTX", "results": r, "result_r": rr, "base_p": [0.6, 0.3]}
            for r, rr in ((["hit", "stop"], [0.5, -1.0]), (["hit", "hit"], [0.5, 2.0]), (["stop", "stop"], [-1.0, -1.0]), (["open", "open"], [None, None]))]
    b = scoreboard(rows)[0]
    assert b["signals"] == 4 and b["open"] == 1
    tp1 = b["targets"][0]
    assert tp1["closed"] == 3 and tp1["hits"] == 2 and tp1["expected_rate"] == pytest.approx(0.6) and tp1["mean_r"] == pytest.approx(0.0)


def test_evaluate_track_list_delete_endpoints(monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.auth import get_current_user
    from app.db import Base, get_db
    from app.main import app
    from app.routers import asset_brief

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    class U:
        id = 7

    m5 = _walk()
    price = float(m5["close"].iloc[-1])
    monkeypatch.setattr(asset_brief, "_m5", lambda key: m5)
    monkeypatch.setattr(asset_brief, "_market", lambda key: {"price": price})
    monkeypatch.setattr(asset_brief, "_events", lambda *a: [])
    from app import response_cache

    response_cache.clear()
    app.dependency_overrides[get_db] = override
    app.dependency_overrides[get_current_user] = lambda: U()
    client = TestClient(app)
    try:
        text = f"OURO COMPRA {price:.2f} SL {price - 3:.2f} TP1 {price + 1.5:.2f} TP2 {price + 6:.2f}"
        r = client.post("/api/signals/evaluate", json={"text": text, "source": "VTX", "balance": 1000, "risk_pct": 1}).json()
        assert r["ok"] and r["tracked_id"] and len(r["targets"]) == 2 and r["sizing"]["risk_money"] == 10
        assert r["targets"][0]["breakeven_p"] == pytest.approx(1 / 1.5)
        bad = client.post("/api/signals/evaluate", json={"text": "ouro compra 4180 alvo 4200"}).json()
        assert bad["ok"] is False and "stop" in bad["error"]
        lst = client.get("/api/signals").json()
        assert len(lst["signals"]) == 1 and lst["scoreboard"][0]["source"] == "VTX"
        assert client.delete(f"/api/signals/{r['tracked_id']}").status_code == 200
        assert client.get("/api/signals").json()["signals"] == []
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        engine.dispose()
