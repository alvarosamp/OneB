import lzma
import struct
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dukascopy_feed as feed  # noqa: E402


def _bi5(records):
    return lzma.compress(b"".join(struct.pack(">5if", *r) for r in records), format=lzma.FORMAT_ALONE)


class _Resp:
    def __init__(self, body, status=200):
        self.body, self.status = body, status

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture(autouse=True)
def _fast(monkeypatch, tmp_path):
    monkeypatch.setattr(feed, "BACKOFF_SECONDS", (0, 0))
    monkeypatch.setattr(feed, "MIN_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(feed, "CACHE", tmp_path / "cache" / "feed")


def test_minute_file_decodes_columns_scale_and_flats(monkeypatch):
    # tempo, abertura, FECHAMENTO, mínima, máxima, volume (milhões); 2ª barra é plana sem volume.
    body = _bi5([(0, 109316, 109330, 109314, 109344, 2.5), (60, 109330, 109330, 109330, 109330, 0.0),
                 (120, 109330, 109341, 109329, 109343, 1.0)])
    urls = []
    monkeypatch.setattr(feed.urllib.request, "urlopen", lambda url, timeout: urls.append(url) or _Resp(body))
    frame = feed.candles("eurusd", "bid", "m1", "2024-01-10", "2024-01-11")
    assert urls == [f"{feed.BASE}/EURUSD/2024/00/10/BID_candles_min_1.bi5"]  # mês com base 0
    assert list(frame["timestamp"]) == [1704844800000, 1704844920000]
    row = frame.iloc[0]
    assert (row.open, row.high, row.low, row.close, row.volume) == (1.09316, 1.09344, 1.09314, 1.0933, 2_500_000)


def test_m5_aggregates_minutes(monkeypatch):
    body = _bi5([(i * 60, 100 + i, 101 + i, 99 + i, 102 + i, 1.0) for i in range(10)])
    monkeypatch.setattr(feed.urllib.request, "urlopen", lambda url, timeout: _Resp(body))
    frame = feed.candles("xauusd", "ask", "m5", "2024-01-10", "2024-01-11")
    assert len(frame) == 2
    first = frame.iloc[0]
    assert (first.open, first.high, first.low, first.close, first.volume) == (0.1, 0.106, 0.099, 0.105, 5_000_000)


def test_404_is_empty_but_network_error_is_unavailable(monkeypatch):
    def not_found(url, timeout):
        raise urllib.error.HTTPError(url, 404, "nf", {}, None)

    monkeypatch.setattr(feed.urllib.request, "urlopen", not_found)
    assert feed.candles("eurusd", "bid", "m1", "2024-01-10", "2024-01-11").empty

    def reset(url, timeout):
        raise ConnectionResetError("reset")

    monkeypatch.setattr(feed.urllib.request, "urlopen", reset)
    with pytest.raises(feed.FeedUnavailable):
        feed.candles("eurusd", "bid", "m1", "2024-01-10", "2024-01-11")


def test_waf_challenge_202_is_never_empty(monkeypatch):
    monkeypatch.setattr(feed.urllib.request, "urlopen", lambda url, timeout: _Resp(b"", status=202))
    with pytest.raises(feed.FeedUnavailable):
        feed.candles("eurusd", "bid", "m1", "2024-01-10", "2024-01-11")


def test_completed_period_is_cached_and_probe_can_skip_cache(monkeypatch, tmp_path):
    (tmp_path / "cache").mkdir()
    calls = []
    body = _bi5([(0, 1000, 1001, 999, 1002, 1.0)])
    monkeypatch.setattr(feed.urllib.request, "urlopen", lambda url, timeout: calls.append(url) or _Resp(body))
    for _ in range(2):
        feed.candles("eurusd", "bid", "m1", "2024-01-10", "2024-01-11")
    assert len(calls) == 1
    feed.candles("eurusd", "bid", "m1", "2024-01-10", "2024-01-11", use_cache=False)
    assert len(calls) == 2


def test_uncalibrated_instrument_fails():
    with pytest.raises(KeyError):
        feed.candles("btcusd", "bid", "d1", "2024-01-01", "2024-02-01")


def test_rate_limit_pauses_then_succeeds(monkeypatch):
    monkeypatch.setattr(feed, "RATE_LIMIT_PAUSES", (0, 0))
    replies = iter([429, 200])
    body = _bi5([(0, 1000, 1001, 999, 1002, 1.0)])

    def urlopen(url, timeout):
        code = next(replies)
        if code == 429:
            raise urllib.error.HTTPError(url, 429, "too many", {}, None)
        return _Resp(body)

    monkeypatch.setattr(feed.urllib.request, "urlopen", urlopen)
    assert len(feed.candles("eurusd", "bid", "m1", "2024-01-10", "2024-01-11")) == 1


def test_persistent_rate_limit_is_unavailable(monkeypatch):
    monkeypatch.setattr(feed, "RATE_LIMIT_PAUSES", (0, 0))

    def urlopen(url, timeout):
        raise urllib.error.HTTPError(url, 429, "too many", {}, None)

    monkeypatch.setattr(feed.urllib.request, "urlopen", urlopen)
    with pytest.raises(feed.FeedUnavailable):
        feed.candles("eurusd", "bid", "m1", "2024-01-10", "2024-01-11")
