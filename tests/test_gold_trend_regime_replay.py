import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from gold_trend_regime_replay import classify,masks


def test_future_quotes_cannot_change_prior_regime():
    times=pd.date_range('2026-05-04',periods=1000,freq='min')
    ticks=pd.DataFrame(dict(time_msc=times.as_unit('ms').asi8,bid=100+np.arange(1000)*.01))
    signal=dict(name='x',decision=pd.Timestamp('2026-05-04 12:00'),side=1)
    before=classify([signal],ticks)[0]
    changed=ticks.copy()
    changed.loc[changed.time_msc>=signal['decision'].value//1_000_000,'bid']=100000
    assert classify([signal],changed)[0]==before
    assert pd.Timestamp(before['feature_close_m5'])<=signal['decision']


def test_unavailable_warmup_never_activates_filter():
    times=pd.date_range('2026-05-04',periods=5,freq='min')
    ticks=pd.DataFrame(dict(time_msc=times.as_unit('ms').asi8,bid=100.))
    labels=classify([dict(name='x',decision=times[-1],side=1)],ticks)[0]
    assert masks(labels)==dict(no_filter=True,trend_M5=False,trend_M15=False,trend_both=False,trend_momentum_M5=False)
