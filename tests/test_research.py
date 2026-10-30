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


def test_news_archive_collect_dedupes_and_survives_failure(tmp_path):
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from app.research import news_archive

    def art(h):
        return SimpleNamespace(published_at=datetime(2026, 1, 1, tzinfo=timezone.utc), source="X", headline=h, url="u")

    def company(sym):
        if sym == "BAD":
            raise RuntimeError("rede")
        return [art(f"{sym} sobe"), art(f"{sym} cai")]

    market = lambda _: [art("Fed mantém juros")]
    first = news_archive.collect(["AAPL", "BAD"], tmp_path, company, market)
    assert first["new"] == 3 and first["total"] == 3  # MARKET + AAPL x2; BAD ignorado
    again = news_archive.collect(["AAPL", "BAD"], tmp_path, company, market)
    assert again["new"] == 0 and again["total"] == 3
    assert set(news_archive.load(tmp_path).symbol) == {"MARKET", "AAPL"}


def test_news_archive_seeds_from_legacy_daily_files(tmp_path):
    pd.DataFrame(
        {"symbol": ["AAPL"], "published_at": ["2026-01-01"], "source": ["Y"], "headline": ["velha"]}
    ).to_csv(tmp_path / "2026-10-29.csv", index=False)
    from app.research import news_archive

    out = news_archive.collect([], tmp_path, lambda s: [], lambda s: [])
    assert out["total"] == 1


def _panel_history(n=300, vol=0.01, seed=5, drift=0.0005):
    rng = np.random.default_rng(seed)
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(drift, vol, n))), index=_idx(n))
    return pd.DataFrame(
        {"open": close, "high": close * 1.005, "low": close * 0.995, "close": close, "volume": 1000.0}
    )


def test_risk_panel_sizing_and_regime():
    from app.research import risk_panel

    h = _panel_history()
    out = risk_panel.build("TEST", h, risk_pct=1.0, today=h.index[-1])
    assert out["regime"]["trend"] in {"up", "down", "sideways"}
    s = out["sizing"]
    assert s["stop_breached"] == (out["price"] <= s["trailing_stop_price"])
    assert any("stop móvel" in a for a in out["alerts"]) == s["stop_breached"]
    # risco de 1% do capital / distância do stop => tamanho da posição
    assert abs(s["position_pct_of_capital"] - min(100, 1.0 / s["stop_distance_pct"] * 100)) < 0.2
    assert out["evidence"] and out["alerts"] is not None


def test_risk_panel_high_vol_reduces_exposure_and_short_history():
    from app.research import risk_panel

    calm = risk_panel.build("A", _panel_history(vol=0.005), today=pd.Timestamp("2025-01-01"))
    wild = risk_panel.build("B", _panel_history(vol=0.04), today=pd.Timestamp("2025-01-01"))
    assert calm["sizing"]["relative_exposure_pct"] == 100
    assert wild["sizing"]["relative_exposure_pct"] < 50
    assert any("acima do alvo" in a for a in wild["alerts"])
    assert "error" in risk_panel.build("C", _panel_history().head(30))


def test_risk_panel_earnings_warning_and_history():
    from app.research import risk_panel

    h = _panel_history()
    past = [h.index[i] + pd.Timedelta(hours=16) for i in (60, 120, 180, 240)]
    jump = h.copy()
    for i in (61, 121, 181, 241):  # reação no dia seguinte (resultado após o fechamento): +8%
        jump.iloc[i:, jump.columns.get_indexer(["open", "high", "low", "close"])] *= 1.08
    future = h.index[-1] + pd.Timedelta(days=3, hours=16)
    table = pd.DataFrame(
        {"Reported EPS": [1.0] * 4 + [np.nan]}, index=pd.DatetimeIndex(past + [future])
    )
    out = risk_panel.build("E", jump, earnings_table=table, today=h.index[-1])
    e = out["earnings"]
    assert e["soon"] and e["days_until"] == 3
    assert e["history"]["events"] == 4 and e["history"]["avg_abs_move_pct"] > 7
    assert any("Resultado trimestral" in a for a in out["alerts"])


def test_risk_panel_news_block():
    from app.research import risk_panel

    h = _panel_history()
    now = h.index[-1]
    arch = pd.DataFrame(
        {
            "symbol": ["E", "E", "OUTRO"],
            "published_at": [(now - pd.Timedelta(days=1)).isoformat() + "+00:00", (now - pd.Timedelta(days=20)).isoformat() + "+00:00", now.isoformat() + "+00:00"],
            "source": ["s"] * 3,
            "headline": ["recente", "antiga", "outra"],
        }
    )
    n = risk_panel.build("E", h, archive=arch, today=now)["news"]
    assert n["count_7d"] == 1 and n["count_30d"] == 2 and n["latest"][0]["headline"] == "recente"


def test_panel_endpoint(monkeypatch):
    from fastapi.testclient import TestClient

    from app.auth import get_current_user
    from app.main import app
    from app.routers import research as r

    app.dependency_overrides[get_current_user] = lambda: "u"
    h = _panel_history()
    h.index = pd.bdate_range(end=pd.Timestamp.now().normalize(), periods=len(h))
    monkeypatch.setattr(r.store, "load", lambda s, *a, **k: h if s == "OK" else h.iloc[0:0])
    monkeypatch.setattr(r.store, "update", lambda s, *a, **k: h if s == "OK" else h.iloc[0:0])
    monkeypatch.setattr(r.earnings, "earnings_table", lambda s: None)
    monkeypatch.setattr(r.news_archive, "load", lambda *a, **k: pd.DataFrame(columns=news_cols()))
    try:
        c = TestClient(app)
        ok = c.get("/api/research/panel/ok?risk_pct=2")
        assert ok.status_code == 200 and ok.json()["sizing"]["risk_pct"] == 2.0
        assert c.get("/api/research/panel/NADA").status_code == 404
        assert c.get("/api/research/panel/A;B").status_code in (404, 422)
        assert c.get("/api/research/panel/OK?risk_pct=0").status_code == 422
    finally:
        app.dependency_overrides.clear()


def news_cols():
    from app.research import news_archive

    return news_archive.COLUMNS


def test_insiders_parse_zip_keeps_open_market_common_stock_only():
    import io
    import zipfile

    from app.research import insiders

    def tsv(df):
        return df.to_csv(sep="\t", index=False)

    sub = pd.DataFrame({
        "ACCESSION_NUMBER": ["a1", "a2", "a3"], "FILING_DATE": ["02-MAR-2020", "03-MAR-2020", "04-MAR-2020"],
        "DOCUMENT_TYPE": ["4", "4", "4/A"], "ISSUERNAME": ["X Corp"] * 3, "ISSUERTRADINGSYMBOL": ["xyz", "xyz", "xyz"]})
    own = pd.DataFrame({"ACCESSION_NUMBER": ["a1", "a2", "a3"], "RPTOWNERNAME": ["Ana", "Bob", "Cy"],
                        "RPTOWNER_RELATIONSHIP": ["Officer"] * 3, "RPTOWNER_TITLE": ["CEO"] * 3})
    tr = pd.DataFrame({
        "ACCESSION_NUMBER": ["a1", "a1", "a2", "a3"], "SECURITY_TITLE": ["Common Stock", "Option", "Common Stock", "Common Stock"],
        "TRANS_DATE": ["28-FEB-2020"] * 4, "TRANS_CODE": ["P", "P", "A", "P"],
        "TRANS_SHARES": ["100", "50", "10", "5"], "TRANS_PRICEPERSHARE": ["10", "1", "1", "1"]})
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("SUBMISSION.tsv", tsv(sub))
        z.writestr("REPORTINGOWNER.tsv", tsv(own))
        z.writestr("NONDERIV_TRANS.tsv", tsv(tr))
    out = insiders.parse_zip(buf.getvalue())
    assert len(out) == 1  # só a compra (P) de ação ordinária no Form 4 original
    r = out.iloc[0]
    assert r.symbol == "XYZ" and r.owner == "Ana" and r.filing_date == pd.Timestamp("2020-03-02") and r.shares == 100


def test_insiders_quarters_range():
    from app.research import insiders

    assert insiders.quarters("2024q3", "2025q2") == ["2024q3", "2024q4", "2025q1", "2025q2"]
