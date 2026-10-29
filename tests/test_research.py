import numpy as np
import pandas as pd

from app.research import correlation, events, regimes, service, store


def _idx(n):
    return pd.bdate_range("2023-01-02", periods=n)


def _prices(n=300, seed=0, **extra):
    rng = np.random.default_rng(seed)
    base = rng.normal(0, 0.01, n)
    data = {
        "A": 100 * np.exp(np.cumsum(base)),
        "B": 50 * np.exp(np.cumsum(base * 0.8 + rng.normal(0, 0.003, n))),  # correlacionado com A
        "C": 70 * np.exp(np.cumsum(rng.normal(0, 0.01, n))),  # independente
    }
    data.update(extra)
    return pd.DataFrame(data, index=_idx(n))


def _ohlcv(close):
    return pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close, "volume": 1000.0}, index=close.index
    )


def test_pair_correlations_finds_correlated_pair_and_rejects_noise():
    pairs = correlation.pair_correlations(correlation.log_returns(_prices()))
    top = pairs.iloc[0]
    assert {top["a"], top["b"]} == {"A", "B"}
    assert top["r"] > 0.8 and bool(top["significant"])
    noise = pairs[(pairs["a"] == "A") & (pairs["b"] == "C")].iloc[0]
    assert abs(noise["r"]) < 0.3
    assert pairs["p_adj"].ge(pairs["p"]).all()


def test_pair_correlations_respects_min_obs():
    pairs = correlation.pair_correlations(correlation.log_returns(_prices(n=30)), min_obs=60)
    assert pairs.empty


def test_benjamini_hochberg_monotonic_and_handles_none():
    adj = correlation.benjamini_hochberg([0.01, 0.04, None, 0.03])
    assert adj[2] is None
    assert adj[0] == 0.03  # 0.01*3/1 = 0.03
    assert all(a >= p for a, p in zip([adj[0], adj[3], adj[1]], [0.01, 0.03, 0.04]))


def test_correlation_drift_detects_broken_relation():
    n = 300
    rng = np.random.default_rng(1)
    a = rng.normal(0, 0.01, n)
    b = np.concatenate([a[:240], rng.normal(0, 0.01, 60)])  # relação some nos últimos 60
    r = pd.DataFrame({"A": a, "B": b}, index=_idx(n))
    drift = correlation.correlation_drift(r, recent=60)
    row = drift.iloc[0]
    assert row["r_full"] > 0.5
    assert row["delta"] < -0.4


def test_lead_lag_identifies_leader():
    rng = np.random.default_rng(2)
    a = pd.Series(rng.normal(0, 0.01, 300), index=_idx(300))
    b = a.shift(2).fillna(0) + rng.normal(0, 0.002, 300)  # b repete a com 2 dias de atraso
    result = correlation.lead_lag(a, b, max_lag=5)
    assert result["best"]["lag"] == 2
    assert result["best"]["r"] > 0.9
    assert result["best"]["p_adj"] < 0.01


def test_trend_regime_up_and_down_without_early_values():
    up = pd.Series(np.linspace(100, 300, 300), index=_idx(300))
    reg = regimes.trend_regime(up)
    assert reg.iloc[:199].isna().all()
    assert reg.iloc[-1] == "up"
    assert regimes.trend_regime(up[::-1].set_axis(up.index)).iloc[-1] == "down"


def test_volatility_regime_flags_high_vol_burst():
    rng = np.random.default_rng(3)
    rets = np.concatenate([rng.normal(0, 0.005, 300), rng.normal(0, 0.04, 25)])
    close = pd.Series(100 * np.exp(np.cumsum(rets)), index=_idx(325))
    assert regimes.volatility_regime(close).iloc[-1] == "high"


def test_regime_summary_run_length():
    close = pd.Series(np.linspace(100, 300, 300), index=_idx(300))
    s = regimes.regime_summary(close)
    assert s["trend"] == "up" and s["trend_label"] == "alta"
    assert 0 < s["trend_bars"] <= 101


def test_forward_return_by_regime_groups():
    close = pd.Series(np.linspace(100, 200, 50), index=_idx(50))
    reg = pd.Series(["up"] * 25 + ["down"] * 25, index=close.index)
    out = regimes.forward_return_by_regime(close, reg, horizon=5)
    assert set(out["regime"]) == {"up", "down"}
    assert (out["hit_rate"] == 1.0).all()


def test_apply_cooldown_collapses_clusters():
    sig = pd.Series([True, True, True, False, False, False, False, True], index=_idx(8))
    out = events.apply_cooldown(sig, cooldown=3)
    assert out.tolist() == [True, False, False, False, False, False, False, True]


def test_event_study_no_lookahead_and_excess():
    # preço sobe 10% nos 5 dias seguintes a cada sinal
    close = pd.Series(100.0, index=_idx(200))
    sig = pd.Series(False, index=close.index)
    for i in range(10, 180, 20):
        sig.iloc[i] = True
        close.iloc[i + 1 :] *= 1.0
        close.iloc[i + 5 :] *= 1.10
    rows = events.event_study(close, sig, horizons=(5,), cooldown=5)
    r = rows[0]
    assert r["n"] == 9
    assert r["mean_pct"] == 10.0 and r["hit_rate"] == 1.0
    assert r["excess_pct"] > 5
    assert r["t_stat"] is None or r["t_stat"] > 2


def test_event_study_no_events():
    close = pd.Series(np.linspace(100, 110, 50), index=_idx(50))
    rows = events.event_study(close, pd.Series(False, index=close.index), horizons=(5,))
    assert rows[0]["n"] == 0 and rows[0]["mean_pct"] is None


def test_store_roundtrip_merge_and_failure(tmp_path):
    close = pd.Series(np.linspace(100, 110, 30), index=pd.bdate_range("2024-01-01", periods=30, tz="UTC"))
    calls = []

    def fetcher(symbol, period, interval):
        calls.append(period)
        return _ohlcv(close) if len(calls) == 1 else _ohlcv(close.iloc[-5:] + 1)

    first = store.update("GC=F", tmp_path, fetcher=fetcher)
    assert len(first) == 30 and calls == ["5y"]
    second = store.update("GC=F", tmp_path, fetcher=fetcher)
    assert calls[-1] == "1mo"
    assert len(second) == 30 and not second.index.has_duplicates
    assert second["close"].iloc[-1] == close.iloc[-1] + 1  # dado novo sobrescreve
    assert (tmp_path / "GC_F.csv").exists()

    # falha de rede mantém o histórico local
    kept = store.update("GC=F", tmp_path, fetcher=lambda *a: pd.DataFrame())
    assert len(kept) == 30


def test_run_study_end_to_end_and_too_few_symbols(tmp_path):
    prices = _prices(n=300)

    def fetcher(symbol, period, interval):
        return _ohlcv(prices[symbol])

    out = service.run_study(["A", "B", "C"], directory=tmp_path, fetcher=fetcher)
    assert out["pairs_tested"] == 3 and out["pairs_significant"] >= 1
    assert set(out["per_symbol"]) == {"A", "B", "C"}
    assert out["per_symbol"]["A"]["regime"]["trend"] in {"up", "down", "sideways"}
    assert out["caveats"]
    assert len(out["matrix"]) == 3 and len(out["matrix"][0]) == 3

    few = service.run_study(["A"], directory=tmp_path / "x", fetcher=fetcher)
    assert "error" in few


def test_study_endpoint_validates_and_runs(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from app.auth import get_current_user
    from app.main import app
    from app.routers import research as research_router

    app.dependency_overrides[get_current_user] = lambda: "test-user"
    captured = {}

    def fake_run_study(symbols, refresh=False, **kw):
        captured.update(symbols=symbols, refresh=refresh)
        return {"symbols": symbols}

    monkeypatch.setattr(research_router.service, "run_study", fake_run_study)
    try:
        c = TestClient(app)
        ok = c.get("/api/research/study?symbols=nvda,AAPL,nvda,GC=F")
        assert ok.status_code == 200
        assert captured["symbols"] == ["NVDA", "AAPL", "GC=F"] and captured["refresh"] is False
        assert c.get("/api/research/study?symbols=A;B").status_code == 422
        many = ",".join(f"S{i}" for i in range(16))
        assert c.get(f"/api/research/study?symbols={many}").status_code == 422
    finally:
        app.dependency_overrides.clear()
