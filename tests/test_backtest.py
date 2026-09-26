import pandas as pd

from app.backtest import backtest_conditions
from app.models import RuleLogic, RuleType
from app.rules_engine import RuleContext


def _history(closes, volumes=None):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="1D")
    volumes = volumes or [1000] * len(closes)
    return pd.DataFrame({"close": closes, "volume": volumes}, index=idx)


def test_backtest_empty_history_returns_zero():
    result = backtest_conditions([RuleContext(RuleType.PRICE_ABOVE, 100, 0, 0)], RuleLogic.ALL, pd.DataFrame())
    assert result.trigger_count == 0
    assert result.avg_forward_return_pct is None
    assert result.occurrences == []


def test_backtest_price_above_counts_every_bar_over_threshold():
    # 40 flat bars at 50, then 10 bars at 200 (all above threshold=150)
    closes = [50.0] * 40 + [200.0] * 10
    history = _history(closes)
    conditions = [RuleContext(RuleType.PRICE_ABOVE, threshold=150, param_a=0, param_b=0)]

    result = backtest_conditions(conditions, RuleLogic.ALL, history, symbol="TEST", forward_bars=2)

    assert result.trigger_count == 10
    assert all(o.price == 200.0 for o in result.occurrences)


def test_backtest_forward_return_is_none_near_end_of_history():
    closes = [50.0] * 40 + [200.0] * 3  # not enough bars after the last trigger for forward_bars=5
    history = _history(closes)
    conditions = [RuleContext(RuleType.PRICE_ABOVE, threshold=150, param_a=0, param_b=0)]

    result = backtest_conditions(conditions, RuleLogic.ALL, history, forward_bars=5)

    last_occurrence = result.occurrences[-1]
    assert last_occurrence.forward_return_pct is None


def test_backtest_computes_average_forward_return():
    # flat at 100 for lookback, one trigger bar at 100, then price doubles forward_bars later
    closes = [100.0] * 31 + [200.0] * 10
    history = _history(closes)
    conditions = [RuleContext(RuleType.PRICE_ABOVE, threshold=99, param_a=0, param_b=0)]

    result = backtest_conditions(conditions, RuleLogic.ALL, history, forward_bars=1)

    assert result.trigger_count > 0
    assert result.avg_forward_return_pct is not None


def test_backtest_no_conditions_returns_zero():
    history = _history([100.0] * 40)
    result = backtest_conditions([], RuleLogic.ALL, history)
    assert result.trigger_count == 0


def test_backtest_respects_max_occurrences():
    closes = [200.0] * 60  # triggers on almost every bar past the lookback
    history = _history(closes)
    conditions = [RuleContext(RuleType.PRICE_ABOVE, threshold=100, param_a=0, param_b=0)]

    result = backtest_conditions(conditions, RuleLogic.ALL, history, max_occurrences=5)

    assert len(result.occurrences) == 5
