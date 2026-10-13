import numpy as np
import pandas as pd

from app import signal_quality as sq


def _trades(n, seed=0, informative=True):
    rng = np.random.default_rng(seed)
    out = []
    start = pd.Timestamp("2026-01-01 10:00")
    for i in range(n):
        signal = rng.normal()
        noise = rng.normal()
        good = (signal + 0.6 * rng.normal() > 0) if informative else (rng.random() > 0.5)
        r = 1.4 if good else -1.0
        out.append({
            "outcome": "TARGET" if good else "STOP", "r": r, "entry_at": (start + pd.Timedelta(hours=6 * i)).isoformat(),
            "features": {"signal": float(signal), "noise": float(noise)},
        })
    return out


def test_refuses_to_train_below_min_events():
    model = sq.train(_trades(80), setup="x", max_hold_minutes=240)
    assert model["status"] == "INSUFFICIENT_EVENTS" and model["promoted"] is False
    assert sq.predict(model, {"signal": 1.0}) is None


def test_informative_feature_gets_promoted_with_interval():
    model = sq.train(_trades(900, seed=1), setup="x", max_hold_minutes=240)
    assert model["status"] == "TRAINED"
    assert model["promoted"], model["promotion_failures"]
    good = sq.predict(model, {"signal": 2.0, "noise": 0.0})
    bad = sq.predict(model, {"signal": -2.0, "noise": 0.0})
    assert good["p_positive"] > 0.7 > 0.3 > bad["p_positive"]
    assert good["interval"][0] <= good["p_positive"] <= good["interval"][1]


def test_pure_noise_is_not_promoted():
    model = sq.train(_trades(600, seed=2, informative=False), setup="x", max_hold_minutes=240)
    assert model["promoted"] is False


def test_split_is_chronological_with_embargo():
    times = [(pd.Timestamp("2026-01-01") + pd.Timedelta(minutes=30 * i)).isoformat() for i in range(100)]
    tr, ca, te = sq.chronological_split(100, times, embargo_minutes=240)
    assert tr.max() < ca.min() < ca.max() < te.min()
    assert ca.min() - tr.max() > 1  # embargo removeu trades colados na fronteira
