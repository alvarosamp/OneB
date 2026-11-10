"""Date-based walk-forward folds for the cross-sectional research scripts.

scripts/calibrate_decision_strategy._walk_forward_folds splits by INTEGER
ROW POSITION into each symbol's own history. That's safe only when every
symbol's history starts on the same calendar date — true for the 24/48
symbol universes tested so far (all long-listed, fetched with the same
`period`), which is why the row_index bug found in this session's data-
phase audit didn't actually corrupt those results (verified directly:
AAPL/PLTR/NVDA/JPM land on the identical calendar date at the same
row_index within the 2-year window).

It stops being safe the moment MARKET_HISTORY_PERIOD is pushed past a
recent IPO's listing date (a few small/mid-cap symbols in this project's
own test universe — DUOL, ONON, CFLT — listed in 2021, right at a 5-year
boundary): row_index N would then point at a different calendar date for
that symbol than for a longer-listed one, silently mixing time periods
within a "fold" and undermining the whole embargo/purging discipline this
project's walk-forward validation is built on.

This module folds on the actual calendar date range instead, so it stays
correct regardless of which symbols have shorter histories.
"""
from __future__ import annotations

import pandas as pd


def date_based_folds(
    dates: pd.Series, num_folds: int, window_days: int, embargo_days: int
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Same walking-forward-windows-with-embargo logic as
    scripts.calibrate_decision_strategy._walk_forward_folds, but the units
    are trading days present in `dates` (the panel's own calendar), not
    row positions into any single symbol's history.

    Returns (start_date, end_date) pairs, end exclusive — filter a panel
    with `(panel["date"] >= start) & (panel["date"] < end)`.
    """
    unique_dates = pd.DatetimeIndex(sorted(pd.to_datetime(dates).unique()))
    max_len = len(unique_dates)
    total_start = max(0, max_len - window_days)
    total_len = max_len - total_start
    fold_len = max(10 + embargo_days, total_len // num_folds)

    folds = []
    for k in range(num_folds):
        raw_start = total_start + k * fold_len
        start_idx = raw_start + embargo_days if k > 0 else raw_start
        end_idx = total_start + (k + 1) * fold_len if k < num_folds - 1 else max_len
        end_idx = min(end_idx, max_len)
        if end_idx - start_idx < 10 or start_idx >= max_len:
            continue
        folds.append((unique_dates[start_idx], unique_dates[min(end_idx, max_len - 1)]))
    return folds
