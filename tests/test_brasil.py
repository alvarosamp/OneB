from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.brasil import events, market, products, rates
from app.brasil.simulator import ALLOCATIONS, SimInput, profile, simulate
from app.main import app

RATES = {"selic": 13.75, "cdi": 13.65, "ipca_12m": 4.58, "stale": False, "series": {"cdi": {"as_of": "2026-10-27"}}}


def _inp(**kw) -> SimInput:
    base = dict(initial=10_000, monthly=500, months=120, goal="aposentadoria", rates=RATES)
    return SimInput(**(base | kw))


def test_ir_table_and_poupanca_rule():
    assert products.ir_rate(30) == 0.225
    assert products.ir_rate(200) == 0.20
    assert products.ir_rate(500) == 0.175
    assert products.ir_rate(721) == 0.15
    assert rates.poupanca_annual(13.75) == pytest.approx(6.17, abs=0.01)  # 0,5% a.m.
    assert rates.poupanca_annual(8.0) == pytest.approx(5.6)  # 70% da Selic


def test_rates_fall_back_and_flag_stale_when_bcb_is_down():
    def boom(code):
        raise RuntimeError("fora do ar")

    out = rates._load(fetch=boom)
    assert out["stale"] is True and out["selic"] == rates.FALLBACK["selic"][0]


def test_allocations_sum_to_100():
    for bucket in ALLOCATIONS.values():
        for alloc in bucket.values():
            assert sum(alloc.values()) == 100


def test_short_horizon_never_gets_stock_market():
    out = simulate(_inp(months=18, goal="objetivo", drop_reaction="comprar", experience="boa"))
    assert out["profile"]["key"] == "conservador"
    assert all(a["group"] == "renda_fixa" for a in out["allocation"])
    assert out["projection"]["has_variable"] is False


def test_selling_in_a_drop_caps_profile():
    p = profile(_inp(months=300, drop_reaction="vender", experience="boa"))
    assert p["key"] == "moderado"


def test_reserve_comes_first_when_missing():
    out = simulate(_inp(initial=3_000, monthly=1_000, has_reserve=False, monthly_expenses=2_000))
    assert out["reserve"] == {"target": 12_000, "months_to_fill": 9}
    assert out["steps"][0]["title"].startswith("1. Monte a reserva")
    # todo o valor inicial foi para a reserva, nada para a divisão do objetivo
    assert all(a["initial_amount"] == 0 for a in out["allocation"])


def test_fixed_income_beats_poupanca_after_tax():
    out = simulate(_inp(initial=10_000, monthly=0, months=24, goal="reserva"))
    proj = out["projection"]
    # Tesouro Selic/CDB a ~13,6% com IR de 15% > poupança isenta a 6,17%
    assert proj["median"] > proj["poupanca"] > proj["invested"]
    assert proj["p10"] == proj["median"] == proj["p90"]  # sem renda variável, sem faixa
    # IR de 15% sobre 2 anos de CDI: líquido ≈ 10.000 × (1 + 0,85 × (1,1365² − 1))
    assert proj["median"] == pytest.approx(10_000 * (1 + 0.85 * (1.1365**2 - 1)), rel=0.01)


def test_variable_projection_is_a_range_and_deterministic():
    a = simulate(_inp(drop_reaction="comprar", experience="boa"))
    b = simulate(_inp(drop_reaction="comprar", experience="boa"))
    pa = a["projection"]
    assert pa["p10"] < pa["median"] < pa["p90"]
    assert pa == b["projection"]
    assert pa["median_today_money"] < pa["median"]
    assert "CVM" in a["disclaimer"]


def test_simulator_never_names_a_ticker():
    out = simulate(_inp(drop_reaction="comprar", experience="boa"))
    text = str(out)
    for ticker in ("BOVA11", "IVVB11", "PETR4", "HGLG11"):
        assert ticker not in text


def test_metrics_cut_series_at_unadjusted_split():
    idx = pd.date_range("2025-01-01", periods=300, freq="B")
    close = pd.Series(np.r_[np.full(150, 0.13), np.full(150, 98.0)], index=idx)
    m = market.metrics(close)
    assert m["data_break"] == idx[150].date().isoformat()
    assert m["return_12m_pct"] == 0.0


def test_ibov_futures_expiry_is_wednesday_near_15th():
    d = events._ibov_futures_expiry(2026, 12)
    assert d.weekday() == 2 and abs((d - date(2026, 12, 15)).days) <= 3


def test_upcoming_events_include_copom_and_elections():
    up = events.upcoming(today=date(2026, 9, 1), days=60)
    kinds = {e["kind"] for e in up}
    assert {"copom", "eleicao", "ipca"} <= kinds
    assert [e["date"] for e in up] == sorted(e["date"] for e in up)


def test_measure_impact_uses_next_session_after_sunday_election():
    idx = pd.bdate_range("2022-09-01", "2022-11-30")
    close = pd.Series(100.0, index=idx)
    close.loc["2022-10-03":] = 110.0  # segunda depois do 1º turno de 02/10/2022
    out = events.measure_impact(pd.DataFrame({"close": close}), copom=[])
    row = next(r for r in out["eleicao"]["rows"] if r["event_date"] == "2022-10-02")
    assert row["session"] == "2022-10-03" and row["return_pct"] == 10.0


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(rates, "current", lambda: RATES)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_simulate_endpoint(client):
    res = client.post("/api/brasil/simulate", json={"initial": 1000, "monthly": 200, "months": 36, "goal": "objetivo"})
    assert res.status_code == 200
    body = res.json()
    assert body["allocation"] and body["projection"]["timeline"][-1]["month"] == 36


def test_simulate_requires_money(client):
    res = client.post("/api/brasil/simulate", json={"initial": 0, "monthly": 0, "months": 12, "goal": "reserva"})
    assert res.status_code == 422


def test_products_endpoint_hides_internal_fields(client):
    body = client.get("/api/brasil/products").json()
    assert len(body["products"]) == len(products.PRODUCTS)
    assert all("tax_rule" not in p and p["risk_label"] for p in body["products"])
