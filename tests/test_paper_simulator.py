import pandas as pd

from app import paper_simulator


def _prepared(price: float = 100.0, sell_signal: bool = False):
    rows = 140
    history = pd.DataFrame(
        {
            "open": [price] * rows,
            "high": [price + 1] * rows,
            "low": [price - 1] * rows,
            "close": [price] * rows,
            "volume": [1000] * rows,
        },
        index=pd.date_range("2026-01-01", periods=rows, freq="D"),
    )
    data = paper_simulator._prepared(history)
    data.update(
        {
            "ema9": pd.Series(([102.0] * rows) if not sell_signal else ([98.0] * rows)),
            "ema21": pd.Series(([100.0] * rows) if not sell_signal else ([100.0] * rows)),
            "rsi": pd.Series([55.0] * rows),
            "macd": pd.DataFrame(
                {
                    "macd": ([2.0] * rows) if not sell_signal else ([-2.0] * rows),
                    "signal": ([1.0] * rows) if not sell_signal else ([-1.0] * rows),
                }
            ),
            "volume_ratio": pd.Series([1.2] * rows),
            "atr": pd.Series([2.0] * rows),
            "annualized_volatility": pd.Series([20.0] * rows),
            "recent_high20": pd.Series([price - 1.0] * rows),
            "return20": pd.Series([5.0] * rows),
        }
    )
    return data


def _capture(monkeypatch, state: dict, selected_filter, calibration: dict, prepared: dict):
    events = []
    saved = []
    monkeypatch.setattr(paper_simulator, "_symbols", lambda: sorted(prepared.keys()) or ["AAPL"])
    monkeypatch.setattr(paper_simulator, "_history", lambda *args, **kwargs: pd.DataFrame())
    monkeypatch.setattr(paper_simulator, "_load_state", lambda: state.copy())
    monkeypatch.setattr(paper_simulator, "_save_state", lambda value: saved.append(value.copy()))
    monkeypatch.setattr(paper_simulator, "calibrate", lambda symbols: (selected_filter, calibration, prepared))
    monkeypatch.setattr(paper_simulator, "_log", lambda event: events.append(event))
    return events, saved


def test_no_trade_when_filter_is_not_reliable(monkeypatch):
    events, saved = _capture(
        monkeypatch,
        {"cash": 10000.0, "initial_capital": 10000.0, "positions": {}, "closed_trades": []},
        None,
        {"status": "not_reliable", "precision_pct": 57.14, "false_positive": 9},
        {"AAPL": _prepared()},
    )
    monkeypatch.setattr(paper_simulator, "_passes_filter", lambda *args, **kwargs: True)
    monkeypatch.setattr(paper_simulator, "_opportunity_score", lambda *args, **kwargs: (82, {"market": {"state": "bullish"}}))

    paper_simulator.evaluate_cycle()

    assert events[-1]["decision"] == "NO_TRADE"
    assert events[-1]["reason"] == "Filtro historico ainda nao confiavel."
    assert saved[-1]["cash"] == 10000.0
    assert saved[-1]["positions"] == {}


def test_buy_when_filter_is_reliable_and_current_signal_passes(monkeypatch):
    reliable_filter = paper_simulator.FilterParams(
        rsi_low=45,
        rsi_high=62,
        min_volume_ratio=1.0,
        max_atr_pct=4.0,
        max_annualized_volatility=35.0,
        min_score=50,
    )
    events, saved = _capture(
        monkeypatch,
        {"cash": 10000.0, "initial_capital": 10000.0, "positions": {}, "closed_trades": []},
        reliable_filter,
        {"status": "reliable", "precision_pct": 62.0, "false_positive": 8},
        {"AAPL": _prepared(price=50.0)},
    )

    paper_simulator.evaluate_cycle()

    buy = next(event for event in events if event["type"] == "buy")
    assert buy["symbol"] == "AAPL"
    assert buy["shares"] > 0
    assert saved[-1]["cash"] < 10000.0
    assert saved[-1]["positions"]["AAPL"]["stop"] < saved[-1]["positions"]["AAPL"]["entry_price"]
    assert saved[-1]["positions"]["AAPL"]["target"] > saved[-1]["positions"]["AAPL"]["entry_price"]


def test_skip_buy_when_capital_cannot_buy_one_whole_share(monkeypatch):
    reliable_filter = paper_simulator.FilterParams(45, 62, 1.0, 4.0, 35.0)
    events, saved = _capture(
        monkeypatch,
        {"cash": 200.0, "initial_capital": 200.0, "positions": {}, "closed_trades": []},
        reliable_filter,
        {"status": "reliable", "precision_pct": 62.0, "false_positive": 8},
        {"AAPL": _prepared(price=250.0)},
    )
    monkeypatch.setattr(paper_simulator, "_passes_filter", lambda *args, **kwargs: True)

    paper_simulator.evaluate_cycle()

    assert any(event.get("decision") == "SKIP" for event in events)
    assert saved[-1]["cash"] == 200.0
    assert saved[-1]["positions"] == {}


def test_sell_open_position_on_stop_hit_even_when_filter_is_not_reliable(monkeypatch):
    state = {
        "cash": 20.0,
        "initial_capital": 200.0,
        "positions": {
            "AAPL": {
                "symbol": "AAPL",
                "entry_at": "2026-08-05T00:00:00+00:00",
                "entry_price": 100.0,
                "shares": 1,
                "stop": 95.0,
                "target": 110.0,
                "filter": {},
            }
        },
        "closed_trades": [],
    }
    events, saved = _capture(
        monkeypatch,
        state,
        None,
        {"status": "not_reliable", "precision_pct": 50.0, "false_positive": 10},
        {"AAPL": _prepared(price=94.0)},
    )

    paper_simulator.evaluate_cycle()

    sell = next(event for event in events if event["type"] == "sell")
    assert sell["reason"] == "stop_hit"
    assert sell["pnl"] < -6.0
    assert saved[-1]["cash"] < 114.0
    assert saved[-1]["positions"] == {}


def test_deep_replay_writes_buy_events(monkeypatch):
    prepared = {"AAPL": _prepared(price=50.0)}
    sell_prepared = _prepared(price=55.0)
    sell_prepared["ema9"] = pd.Series([98.0] * 90)
    sell_prepared["ema21"] = pd.Series([100.0] * 90)

    calls = {"count": 0}

    def fake_calibrate_until(_prepared_data, _end_index_by_symbol, _benchmark=None):
        calls["count"] += 1
        params = paper_simulator.FilterParams(45, 62, 1.0, 4.0, 35.0)
        return params, {"status": "reliable", "signals": 12, "precision_pct": 60.0, "avg_5d_return_pct": 1.0}

    events = []
    monkeypatch.setattr(paper_simulator, "_symbols", lambda: ["AAPL"])
    monkeypatch.setattr(paper_simulator, "_history", lambda symbol: prepared.get(symbol, prepared["AAPL"])["history"])
    monkeypatch.setattr(paper_simulator, "_prepared", lambda history: prepared["AAPL"] if calls["count"] < 1 else sell_prepared)
    monkeypatch.setattr(paper_simulator, "_calibrate_until", fake_calibrate_until)
    monkeypatch.setattr(paper_simulator, "_passes_filter", lambda *args, **kwargs: True)
    monkeypatch.setattr(paper_simulator, "_opportunity_score", lambda *args, **kwargs: (82, {"market": {"state": "bullish"}}))
    monkeypatch.setattr(paper_simulator, "_market_regime", lambda *args, **kwargs: {"state": "bullish", "risk_multiplier": 1.0, "score": 25})
    monkeypatch.setattr(paper_simulator, "_save_deep_replay", lambda result: None)
    monkeypatch.setattr(paper_simulator, "_log", lambda event: events.append(event))

    result = paper_simulator.run_deep_replay(initial_capital=10000.0, replay_days=20)

    assert result["status"] == "completed"
    assert result["buys"] >= 1
    assert result["total_events"] >= 1
