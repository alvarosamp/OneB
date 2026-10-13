import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from backtest_original_13x_ticks import events_from_buffers, simulate


def test_excludes_seeded_forming_and_zero_buffers(tmp_path):
    path=tmp_path/'audit.csv'
    path.write_text('observed_at;bar_time;shift;buffer;status;value;error\n'
        '2026.05.04 01:00:00;2026.05.01 23:55:00;1;2;ok;100;0\n'
        '2026.05.04 01:05:00;2026.05.04 01:00:00;1;2;ok;100;0\n'
        '2026.05.04 01:05:00;2026.05.04 01:05:00;0;3;ok;101;0\n'
        '2026.05.04 01:05:00;2026.05.04 01:00:00;1;4;ok;0;0\n',encoding='utf-8')
    events=events_from_buffers(path)
    assert len(events)==1 and events[0]['buffers']=={2}


def test_exits_only_after_observed_exit_not_arrow_price():
    start=pd.Timestamp('2026-05-04')
    t=start.value//1_000_000
    ticks=pd.DataFrame(dict(time_msc=[t,t+250,t+1000,t+1250],bid=[100,100,101,102],ask=[100.3,100.3,101.3,102.3]))
    events=[dict(time=start,buffers={2}),dict(time=start+pd.Timedelta(seconds=1),buffers={4})]
    result=simulate(events,ticks)
    trade=result['trades'][0]
    assert trade['exit_time_msc']==t+1250
    assert trade['reason']=='vendor_exit_buffer'
    assert abs(trade['net_pnl_per_ounce']-1.5)<1e-9
