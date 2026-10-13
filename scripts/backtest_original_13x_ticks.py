"""Original 13X buffer replay with explicitly provisional entry mapping.

Data Window: EMA13, Compra13X, Venda13X, SaidaLong, SaidaShort.
Buffers0/1 colored EMA;2/3 entries;4/5 exits. Exits numerically cross-checked.
Entry direction still requires numeric visual confirmation: never promote this replay.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd


def events_from_buffers(path):
    f=pd.read_csv(path,sep=';')
    if not f.observed_at.is_monotonic_increasing:
        raise ValueError('Nonchronological observations')
    initial=f.observed_at.iloc[0]
    # Only completed immediately preceding bars. Zero means absent for these plots.
    f=f[(f['shift']==1)&(f.status=='ok')&(f.value>0)&(f.buffer.isin([2,3,4,5]))]
    f=f[f.observed_at != initial].drop_duplicates(['bar_time','buffer'],keep='first')
    events=[]
    for time,g in f.groupby('observed_at',sort=True):
        events.append(dict(time=pd.Timestamp(time),buffers=set(g.buffer.astype(int))))
    return events


def simulate(events,ticks,latency_ms=250,slippage=.05,commission=.1,hold_hours=4):
    times=ticks.time_msc.to_numpy(np.int64)
    bid,ask=ticks.bid.to_numpy(float),ticks.ask.to_numpy(float)
    if not len(times) or (np.diff(times)<0).any() or not np.isfinite(np.r_[bid,ask]).all() or (bid<=0).any() or (ask<bid).any():
        raise ValueError('Invalid tick chronology/quotes')
    trades,excluded,busy=[],[],-1
    for event in events:
        decision=event['time'].value//1_000_000
        if decision<=busy:
            continue
        active=[side for buffer,side in ((2,1),(3,-1)) if buffer in event['buffers']]
        if len(active)!=1:
            continue
        side=active[0]
        i=int(np.searchsorted(times,decision+latency_ms))
        if i==len(times) or times[i]-decision-latency_ms>5000:
            excluded.append(dict(decision=str(event['time']),reason='missing_entry_quote'))
            continue
        deadline=int(times[i]+hold_hours*3600000)
        close_event=next((e for e in events if decision<e['time'].value//1_000_000<deadline and
                         (4 if side==1 else 5) in e['buffers']),None)
        requested_exit=deadline if close_event is None else close_event['time'].value//1_000_000+latency_ms
        j=int(np.searchsorted(times,requested_exit))
        reason='time_stop_hypothesis' if close_event is None else 'vendor_exit_buffer'
        if j==len(times) or times[j]-requested_exit>5000 or (np.diff(times[i:j+1])>60000).any():
            excluded.append(dict(decision=str(event['time']),reason='censored_quote_gap_or_end'))
            busy=requested_exit
            continue
        entry=(ask[i] if side==1 else bid[i])+side*slippage
        exit_price=(bid[j] if side==1 else ask[j])-side*slippage
        path=side*((bid[i:j+1] if side==1 else ask[i:j+1])-side*slippage-entry)-commission
        trades.append(dict(decision=str(event['time']),side=side,entry=entry,exit=exit_price,
            entry_time_msc=int(times[i]),exit_time_msc=int(times[j]),net_pnl_per_ounce=float(side*(exit_price-entry)-commission),
            maximum_adverse_pnl_per_ounce=float(path.min()),maximum_favorable_pnl_per_ounce=float(path.max()),reason=reason))
        busy=times[j]
    pnl=np.array([t['net_pnl_per_ounce'] for t in trades])
    loss=-pnl[pnl<0].sum()
    return dict(trades=trades,excluded=excluded,metrics=dict(trades=len(pnl),net_pnl_per_ounce=float(pnl.sum()),
        expectancy_per_ounce=float(pnl.mean()) if len(pnl) else None,
        profit_factor=float(pnl[pnl>0].sum()/loss) if loss else None),
        assumptions=dict(latency_ms=latency_ms,slippage_price_per_side=slippage,
                         commission_roundtrip_per_ounce=commission,max_hold_hours_hypothesis=hold_hours),
        classification='experimental',entry_mapping='provisional_not_certified')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--buffers',type=Path,required=True)
    p.add_argument('--ticks',type=Path,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    ticks=pd.concat([pd.read_csv(f) for f in a.ticks],ignore_index=True).drop_duplicates().sort_values('time_msc',kind='stable')
    events=events_from_buffers(a.buffers)
    report=dict(events=len(events),tick_rows=len(ticks),scenarios=[simulate(events,ticks,l,s,c)
        for l in (0,250,1000) for s,c in ((0,0),(.05,.1),(.15,.3))],
        sources=[dict(path=str(f.resolve()),sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in [a.buffers,*a.ticks]],
        warning='Actual EX5 values with provisional direction mapping, not certified original strategy performance. '
                'One position, ignore opposing entries until exit, no fixed stop, max hold4h hypothesis. '
                'No orders; no swaps; raw broker clocks. Quote gaps censor trades. Too short for confidence.')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps([dict(assumptions=r['assumptions'],metrics=r['metrics'],excluded=len(r['excluded'])) for r in report['scenarios']],indent=2))


if __name__=='__main__':
    main()
