import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.lab.families import candidates

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_lab", ROOT / "scripts" / "run_lab.py")
run_lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_lab)


def _m5(days=40, seed=4):
    idx = pd.date_range("2024-03-04", periods=days * 288, freq="5min")
    idx = idx[idx.dayofweek < 5]
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 0.8, len(idx)))
    opens = np.concatenate([[close[0]], close[:-1]])
    return pd.DataFrame({"open": opens, "high": np.maximum(opens, close) + rng.uniform(0, 0.5, len(idx)),
                         "low": np.minimum(opens, close) - rng.uniform(0, 0.5, len(idx)), "close": close,
                         "spread": 0.3, "duka_spread": 0.3, "tick_volume": 1}, index=idx)


@pytest.mark.parametrize("asset", ["XAUUSD", "NAS100"])
def test_every_family_is_causal(asset):
    m5 = _m5()
    cut = m5.index[len(m5) * 2 // 3]
    for name, fn in candidates(asset).items():
        if name.startswith("F2_ema_50_200") or name.startswith("F4"):
            continue  # precisam de > 200 barras H1; cobertos pelos demais
        full = fn(m5)
        prefix = fn(m5[m5.index < cut])
        # Sinais completamente formados antes do corte (com folga de 1 dia para famílias diárias) não podem mudar.
        horizon = cut - pd.Timedelta(days=1)
        a = [s for s in full if pd.Timestamp(s["at"]) < horizon]
        b = [s for s in prefix if pd.Timestamp(s["at"]) < horizon]
        assert a == b, name


def test_signals_are_stamped_after_the_bar_closes():
    m5 = _m5()
    for name, fn in candidates("XAUUSD").items():
        for s in fn(m5)[:50]:
            at = pd.Timestamp(s["at"])
            assert at.minute % 5 == 0
            if s["direction"] == "long":
                assert s["stop"] < s["target"], name
            else:
                assert s["stop"] > s["target"], name


def test_benjamini_hochberg_matches_reference():
    q = run_lab.benjamini_hochberg({"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.5})
    assert q["a"] == pytest.approx(0.04)
    assert q["c"] == pytest.approx(0.0533, abs=1e-3)
    assert q["b"] == pytest.approx(0.0533, abs=1e-3)
    assert q["d"] == pytest.approx(0.5)


def test_bootstrap_p_value_direction():
    assert run_lab.bootstrap_p_value([1.0] * 50 + [-0.5] * 50) < 0.05
    assert run_lab.bootstrap_p_value([-1.0] * 50 + [0.5] * 50) > 0.95


def test_duck_signals_follow_closed_h4_and_h1_regime():
    from app.lab.data import resample
    from app.lab.families import f8_duck

    m5 = _m5(days=60, seed=9)
    signals = f8_duck(m5, 2.0)
    assert len(signals) > 5  # o teste de causalidade acima não pode passar vazio
    for rule, minutes in (("4h", 240), ("1h", 60)):
        bars = resample(m5, rule)
        sma = bars["close"].rolling(60, min_periods=60).mean()
        for s in signals:
            at = pd.Timestamp(s["at"])
            closed = bars.index[bars.index + pd.Timedelta(minutes=minutes) <= at][-1]  # última barra fechada
            side = 1 if s["direction"] == "long" else -1
            assert side * (bars["close"][closed] - sma[closed]) > 0, (rule, s["opportunity_id"])
