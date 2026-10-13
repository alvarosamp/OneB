"""Session-block inference for research; does not change legacy study results.

Resample consecutive UTC sessions, keeping contemporaneous events together.
The one-sided p-value resamples under H0 (mean=0), with finite Monte Carlo
correction. Paired policies use the same blocks, with rejected events worth 0R.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def session_block_statistics(
    returns,
    times,
    *,
    accepted=None,
    sessions=None,
    block_sessions: int = 5,
    resamples: int = 10_000,
    seed: int = 7,
    alpha: float = 0.05,
) -> dict:
    values = np.asarray(returns, dtype=float)
    dates = pd.DatetimeIndex(pd.to_datetime(list(times), utc=True)).normalize()
    if values.ndim != 1 or len(values) != len(dates) or not np.isfinite(values).all() or dates.hasnans:
        raise ValueError("Returns and timestamps must be aligned and finite.")
    if block_sessions < 1 or resamples < 1 or not 0 < alpha < 1:
        raise ValueError("Invalid bootstrap settings.")
    mask = np.ones(len(values), dtype=bool) if accepted is None else np.asarray(accepted, dtype=bool)
    if mask.shape != values.shape:
        raise ValueError("Acceptance mask must align with returns.")
    universe = dates.unique().sort_values() if sessions is None else pd.DatetimeIndex(
        pd.to_datetime(list(sessions), utc=True)
    ).normalize().unique().sort_values()
    if universe.hasnans or not dates.isin(universe).all():
        raise ValueError("Session universe does not contain all events.")
    n = len(universe)
    report = {
        "method": "moving-session-block-v2", "sessions": n, "block_sessions": block_sessions,
        "resamples": resamples, "seed": seed, "alpha": alpha,
        "mean_ci": None, "p_value": None, "accepted_mean_ci": None,
        "accepted_minus_all_ci": None, "policy_delta_ci": None,
        "policy_delta_r_per_session": None,
    }
    # One trading day with hundreds of signals is not hundreds of independent samples.
    if not len(values) or n < max(10, 2 * block_sessions):
        report["reason"] = "insufficient_independent_sessions"
        return report
    positions = universe.get_indexer(dates)
    totals = np.bincount(positions, weights=values, minlength=n)
    counts = np.bincount(positions, minlength=n)
    selected_totals = np.bincount(positions[mask], weights=values[mask], minlength=n)
    selected_counts = np.bincount(positions[mask], minlength=n)
    rng = np.random.default_rng(seed)
    draws, selected_draws, differences, policy_deltas = [], [], [], []
    blocks_per_draw = (n + block_sessions - 1) // block_sessions
    offsets = np.arange(block_sessions)
    for start in range(0, resamples, 256):
        batch = min(256, resamples - start)
        starts = rng.integers(0, n - block_sessions + 1, size=(batch, blocks_per_draw))
        indices = (starts[..., None] + offsets).reshape(batch, -1)[:, :n]
        sums, nums = totals[indices].sum(axis=1), counts[indices].sum(axis=1)
        selected_sums = selected_totals[indices].sum(axis=1)
        selected_nums = selected_counts[indices].sum(axis=1)
        valid = nums > 0
        means = sums[valid] / nums[valid]
        draws.extend(means)
        both = valid & (selected_nums > 0)
        selected_means = selected_sums[both] / selected_nums[both]
        selected_draws.extend(selected_means)
        differences.extend(selected_means - sums[both] / nums[both])
        policy_deltas.extend((selected_sums - sums) / n)

    def interval(samples):
        # Do not silently discard most resamples of a very sparse accepted policy.
        if len(samples) < 0.95 * resamples:
            return None
        return np.quantile(samples, [alpha / 2, 1 - alpha / 2]).tolist()

    mean = float(values.mean())
    report["mean_ci"] = interval(draws)
    if report["mean_ci"] is not None:
        null_draws = np.asarray(draws) - mean
        report["p_value"] = float((1 + np.count_nonzero(null_draws >= mean)) / (1 + len(draws)))
    report["accepted_mean_ci"] = interval(selected_draws)
    report["accepted_minus_all_ci"] = interval(differences)
    report["policy_delta_ci"] = interval(policy_deltas)
    report["policy_delta_r_per_session"] = float((selected_totals - totals).mean())
    return report
