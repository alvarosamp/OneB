from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.nasdaq_gold_feature_research import ResearchConfig, _base_features, _context_features, build_dataset, temporal_split


def _history(rows: int = 1400) -> pd.DataFrame:
    index = pd.bdate_range("2015-01-01", periods=rows, tz="UTC")
    close = pd.Series(100 * np.exp(np.linspace(0, 0.5, rows) + 0.01 * np.sin(np.arange(rows) / 7)), index=index)
    return pd.DataFrame(
        {
            "open": close.shift(1).fillna(close.iloc[0]),
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": 1_000_000 + (np.arange(rows) % 20) * 10_000,
        },
        index=index,
    )


def test_base_features_do_not_change_when_future_is_perturbed():
    history = _history(400)
    original = _base_features(history)
    changed = history.copy()
    changed.iloc[300:, changed.columns.get_loc("close")] *= 3
    perturbed = _base_features(changed)
    pd.testing.assert_frame_equal(original.iloc[:300], perturbed.iloc[:300])


def test_label_uses_next_open_not_decision_close():
    history = _history()
    context = {symbol: history.copy() for symbol in ["^VIX", "DX-Y.NYB", "^TNX", "SMH", "SPY", "RSP", "TLT", "IEF", "TIP", "SLV", "CL=F", "GLD"]}
    config = ResearchConfig(horizon=5)
    dataset = build_dataset(history, context, "nasdaq", config)
    timestamp = dataset.index[200]
    position = history.index.get_loc(timestamp)
    expected = history["open"].iloc[position + 6] / history["open"].iloc[position + 1] - 1
    assert dataset.loc[timestamp, "target_gross_return"] == expected


def test_temporal_split_has_embargo_and_untouched_holdout():
    history = _history(2200)
    dataset = _base_features(history).dropna().copy()
    dataset["target_gross_return"] = 0.01
    dataset["target_net_return"] = 0.0086
    dataset["target_up"] = 1.0
    dataset["regime"] = "up_calm"
    config = ResearchConfig(min_train_bars=500, development_folds=4, holdout_years=2)
    dev, test, folds = temporal_split(dataset, config)
    assert dev.index.max() < test.index.min()
    for train, validation in folds:
        assert train.max() + config.horizon < validation.min()


def test_official_macro_features_are_lagged_one_day():
    history = _history(400)
    context = {symbol: history.copy() for symbol in ["^VIX", "DX-Y.NYB", "^TNX", "SMH", "SPY", "RSP", "TLT"]}
    macro = history.copy()
    macro["close"] = np.arange(len(macro), dtype=float)
    context["DGS2"] = macro
    context["DGS10"] = macro.assign(close=macro["close"] + 1.0)

    features = _context_features(history.index, context, "nasdaq")
    timestamp = history.index[100]
    assert features.loc[timestamp, "macro_us2y_chg1"] == 1.0

    changed = context["DGS2"].copy()
    changed.loc[timestamp, "close"] = 10_000.0
    changed_context = {**context, "DGS2": changed}
    changed_features = _context_features(history.index, changed_context, "nasdaq")
    assert changed_features.loc[timestamp, "macro_us2y_chg1"] == features.loc[timestamp, "macro_us2y_chg1"]
