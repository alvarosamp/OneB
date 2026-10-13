import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from walkforward_execution_research import simulate, aggregate


def test_next_completed_bar_ask_entry_and_stop_first():
    index = pd.date_range('2025-01-02 12:00', periods=3, freq='5min', tz='UTC')
    f = pd.DataFrame({'atr':[1.]*3}, index=index)
    for side in ('bid','ask'):
        for field,value in [('open',100.),('high',103.),('low',98.),('close',100.)]:
            f[side+'_'+field]=value+(.3 if side=='ask' else 0)
    sig = pd.Series([1,0,0], index=index)
    out = simulate(f,sig,5,index[0],index[-1]+pd.Timedelta(minutes=5),slippage=0,commission=0)
    assert out[0]['decision'] == str(index[1])
    assert out[0]['reason']=='stop'
    assert abs(out[0]['net']+1)<1e-9


def test_partial_timeframe_is_not_complete():
    index=pd.date_range('2025-01-02',periods=3,freq='5min',tz='UTC')
    frame=pd.DataFrame({'volume':1},index=index)
    for prefix in ('','bid_','ask_'):
        for field in ('open','high','low','close'):
            frame[prefix+field]=100.
    assert len(aggregate(frame,10))==1
