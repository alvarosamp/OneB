import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from replicate_gold_trend_rule import verify_features_config,breakdown


def test_different_parameters_cannot_silently_replicate():
    config=dict(m5_ema_fast=5,m5_ema_slow=20,m15_ema_fast=20,m15_ema_slow=50,slope_bars=3,
                no_optimization=True,primary_rule='trend_both')
    verify_features_config(config)
    config['m15_ema_slow']=49
    with pytest.raises(ValueError):
        verify_features_config(config)


def test_day_side_totals_reconcile():
    trades=[dict(decision='2026-05-11 10:00',side=1,net_pnl_per_ounce=2.),
            dict(decision='2026-05-12 10:00',side=-1,net_pnl_per_ounce=-3.)]
    b=breakdown(trades)
    assert sum(x['net_pnl_per_ounce'] for x in b['day'].values()) == -1.
    assert sum(x['net_pnl_per_ounce'] for x in b['side'].values()) == -1.
