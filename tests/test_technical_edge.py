import numpy as np
import pandas as pd

from app.technical_edge import FEATURE_DIRECTIONS, feature_frame, rank_latest


def _history(start: float, drift: float) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=90, freq="B")
    close = pd.Series(start + np.arange(len(index)) * drift, index=index)
    return pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1_000_000}, index=index)


def test_feature_frame_contains_the_audited_features():
    result = feature_frame(_history(100, 0.4), _history(300, 0.2))
    assert set(FEATURE_DIRECTIONS).issubset(result.columns)
    assert result.iloc[-1].notna().all()


def test_rank_latest_ranks_only_symbols_with_sufficient_history():
    benchmark = _history(300, 0.2)
    rows = rank_latest({"AAA": _history(100, 0.4), "BBB": _history(110, 0.1), "NEW": _history(20, 0.2).head(10)}, benchmark)
    assert {row["symbol"] for row in rows} == {"AAA", "BBB", "NEW"}
    assert [row["rank"] for row in rows if row["status"] == "OK"] == [1, 2]
    assert next(row for row in rows if row["symbol"] == "NEW")["status"] == "SEM_LEITURA"
