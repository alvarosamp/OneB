from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import numpy as np
import pandas as pd

from app.research_dataset import ResearchDatasetConfig, build_research_dataset


def _history(symbol: str, periods: int = 360) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=periods, tz="UTC")
    base = 100 + np.arange(periods) * 0.12
    wobble = np.sin(np.arange(periods) / 9) * 1.5
    if symbol == "MSFT":
        base = base * 1.05
    close = base + wobble
    return pd.DataFrame(
        {
            "open": close - 0.2,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000_000 + (np.arange(periods) % 20) * 10_000,
        },
        index=dates,
    )


def _workspace_tmp() -> Path:
    path = Path("tmp") / "research_dataset_tests" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_build_research_dataset_creates_features_labels_and_time_splits(monkeypatch):
    def fake_get_bars(symbol: str, **_kwargs):
        frame = _history(symbol)
        frame.attrs["provider"] = "fake"
        return frame

    monkeypatch.setattr("app.research_dataset.market_data_service.get_bars", fake_get_bars)
    config = ResearchDatasetConfig(
        symbols=["AAPL", "MSFT"],
        benchmark_symbol="QQQ",
        period="2y",
        min_rows=200,
        output_dir=_workspace_tmp(),
    )

    panel, summary = build_research_dataset(config)

    assert not panel.empty
    assert {"rsi14", "adx14", "rel_ret_5d_vs_benchmark", "fwd_return_5d", "fwd_drawdown_5d", "label_5d"}.issubset(panel.columns)
    assert panel[summary["feature_columns"]].isna().sum().sum() == 0
    assert set(panel["split"]) == {"train", "validation", "test", "purged"}
    assert (panel["split"] == "purged").any()
    assert panel.loc[panel["split"] == "train", "date"].max() < panel.loc[panel["split"] == "test", "date"].min()
    assert summary["dataset_quality"]["status"] in {"PASS", "WARN"}
    assert (config.output_dir / "research_dataset_v1.csv").exists()
    assert (config.output_dir / "research_dataset_v1.summary.json").exists()


def test_build_research_dataset_skips_symbols_without_enough_history(monkeypatch):
    def fake_get_bars(symbol: str, **_kwargs):
        periods = 360 if symbol in {"AAPL", "QQQ"} else 30
        frame = _history(symbol, periods=periods)
        frame.attrs["provider"] = "fake"
        return frame

    monkeypatch.setattr("app.research_dataset.market_data_service.get_bars", fake_get_bars)
    config = ResearchDatasetConfig(
        symbols=["AAPL", "THIN"],
        benchmark_symbol="QQQ",
        period="2y",
        min_rows=200,
        output_dir=_workspace_tmp(),
    )

    panel, summary = build_research_dataset(config, write=False)

    assert set(panel["symbol"]) == {"AAPL"}
    thin = next(row for row in summary["coverage"] if row["symbol"] == "THIN")
    assert thin["status"] == "FAIL"
    assert "INSUFFICIENT_HISTORY" in thin["issues"]
