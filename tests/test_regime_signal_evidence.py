import numpy as np
import pandas as pd

from scripts.regime_signal_evidence import auc, date_block_bootstrap, within_date_permutation_pvalue


def _holdout() -> pd.DataFrame:
    dates = np.repeat(pd.date_range("2025-01-02", periods=8, freq="B"), 4)
    labels = np.tile([0, 0, 1, 1], 8)
    # Perfect cross-sectional ordering, repeated on each independent date.
    scores = np.tile([0.1, 0.3, 0.7, 0.9], 8)
    return pd.DataFrame({"date": dates, "label": labels, "score": scores})


def test_auc_has_expected_rank_interpretation():
    assert auc(np.array([0, 0, 1, 1]), np.array([0.1, 0.2, 0.7, 0.9])) == 1.0
    assert auc(np.array([0, 0, 1, 1]), np.array([0.9, 0.7, 0.2, 0.1])) == 0.0


def test_date_block_bootstrap_is_deterministic_and_returns_auc_ci():
    result = date_block_bootstrap(_holdout(), ["score"], iterations=100, seed=7)
    assert result["score"]["auc"] == [1.0, 1.0]
    assert result["score"]["brier"][0] is not None


def test_within_date_permutation_rejects_perfect_score():
    p_value = within_date_permutation_pvalue(_holdout(), "score", iterations=500, seed=3)
    assert p_value is not None
    assert p_value < 0.05
