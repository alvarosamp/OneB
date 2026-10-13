import importlib.util
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("duka", ROOT / "scripts" / "download_dukascopy_intraday.py")
duka = importlib.util.module_from_spec(spec)
spec.loader.exec_module(duka)


def _write(tmp_path, days):
    stamps = [pd.Timestamp(d) + pd.Timedelta(minutes=5 * i) for d in days for i in range(200)]
    frame = pd.DataFrame({"timestamp": [int(t.value // 1_000_000) for t in stamps], "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1})
    path = tmp_path / "chunk.csv"
    frame.to_csv(path, index=False)
    return path


def test_good_friday_and_year_end_are_market_closed():
    assert duka._easter(2024) == date(2024, 3, 31)
    assert duka._market_closed(date(2024, 3, 29))  # Sexta-feira Santa
    assert duka._market_closed(date(2025, 12, 25))
    assert not duka._market_closed(date(2025, 3, 3))


def test_internal_gap_is_detected_not_just_edges(tmp_path):
    days = [d for d in pd.date_range("2025-03-03", "2025-03-14") if d.dayofweek < 5 and d.day != 6]
    path = _write(tmp_path, days)
    assert duka.missing_weekdays(path, "2025-03-03", "2025-03-15") == ["2025-03-06"]
    assert duka.missing_weekdays(path, "2025-03-03", "2025-03-15", known_gaps={date(2025, 3, 6)}) == []


def test_missing_file_is_incomplete(tmp_path):
    assert duka.missing_weekdays(tmp_path / "nope.csv", "2025-03-03", "2025-03-04") == ["arquivo_ausente"]


def _probes(monkeypatch, answers, healthy=True):
    seq = iter(answers)
    monkeypatch.setattr(duka, "_probe_day_rows", lambda *a, **k: next(seq))
    monkeypatch.setattr(duka.time, "sleep", lambda s: None)
    monkeypatch.setattr(duka.canary.time, "sleep", lambda s: None)
    monkeypatch.setattr(duka.canary, "_last_ok", 0.0)
    monkeypatch.setattr(duka.canary, "canary_rows", lambda: 288 if healthy else 0)


def test_gap_needs_all_probes_to_agree(monkeypatch, tmp_path):
    # Vazio sob limite de requisições e depois dados: NÃO é lacuna (caso EURUSD 02/04/2025).
    _probes(monkeypatch, [0, 288])
    assert duka._confirmed_day_rows("EURUSD", "bid", "m5", date(2025, 4, 2), tmp_path) == 288
    _probes(monkeypatch, [0, 0, 0])
    assert duka._confirmed_day_rows("EURUSD", "bid", "m5", date(2025, 4, 2), tmp_path) == 0
    _probes(monkeypatch, [0, 1, 0])
    assert duka._confirmed_day_rows("EURUSD", "bid", "m5", date(2025, 4, 2), tmp_path) is None
    _probes(monkeypatch, [0, None])
    assert duka._confirmed_day_rows("EURUSD", "bid", "m5", date(2025, 4, 2), tmp_path) is None


def test_cache_files_match_dukascopy_node_naming(tmp_path):
    hit = tmp_path / "candles%2Fminute%2FEUR-USD%2FBID%2F2024%2F12%2F3.json"
    other = tmp_path / "candles%2Fminute%2FEUR-USD%2FBID%2F2024%2F12%2F13.json"
    hit.write_text("{}"), other.write_text("{}")
    assert duka._cache_files(tmp_path, "EURUSD", "bid", date(2024, 12, 3)) == [hit]


def test_probe_ignores_flat_filler_bars(monkeypatch, tmp_path):
    # Feriado: o feed devolve 288 barras, mas quase todas planas (sem negociação).
    bars = pd.DataFrame({"timestamp": range(288), "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
    bars.loc[:9, "high"] = 1.1
    seen = {}

    def fake_candles(*args, **kw):
        seen.update(kw)
        return bars

    monkeypatch.setattr(duka.feed, "candles", fake_candles)
    assert duka._probe_day_rows("NAS100", "ask", "m5", date(2023, 7, 4), tmp_path) == 10
    assert seen["use_cache"] is False  # prova nunca lê o cache


def test_probe_failure_is_not_an_empty_day(monkeypatch, tmp_path):
    def unavailable(*a, **k):
        raise duka.feed.FeedUnavailable("rede")

    monkeypatch.setattr(duka.feed, "candles", unavailable)
    assert duka._probe_day_rows("NAS100", "ask", "m5", date(2023, 7, 4), tmp_path) is None


def test_blocked_source_never_becomes_a_gap(monkeypatch, tmp_path):
    # Fonte devolvendo vazio até para o canário: não registra lacuna, falha com SourceBlocked.
    _probes(monkeypatch, [0, 0, 0], healthy=False)
    import pytest
    with pytest.raises(duka.canary.SourceBlocked):
        duka._confirmed_day_rows("WTI", "ask", "m5", date(2020, 8, 12), tmp_path)
