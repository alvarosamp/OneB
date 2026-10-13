"""Causal trend gates on observed original Gold signals, without live execution.

These dates were previously examined: temporal split is exploratory, NOT untouched OOS.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from backtest_original_gold_ticks import signals_from_objects, simulate
from backtest_original_13x_ticks import events_from_buffers, simulate as simulate_13x


def trend_features(ticks, minutes, fast, slow):
    series=pd.Series(ticks.bid.to_numpy(),index=pd.to_datetime(ticks.time_msc,unit='ms'))
    bars=series.resample(f'{minutes}min',closed='left',label='right').ohlc().dropna()
    ema_fast=bars.close.ewm(span=fast,adjust=False,min_periods=fast).mean()
    ema_slow=bars.close.ewm(span=slow,adjust=False,min_periods=slow).mean()
    direction=np.sign(ema_fast-ema_slow)
    slope=np.sign(ema_slow-ema_slow.shift(3))
    momentum=np.sign(bars.close-bars.close.shift(3))
    return pd.DataFrame(dict(direction=direction,slope=slope,momentum=momentum))


def classify(signals,ticks):
    m5=trend_features(ticks,5,5,20)
    m15=trend_features(ticks,15,20,50)
    rows=[]
    for s in signals:
        decision=s['decision']
        parts=[]
        for f in (m5,m15):
            pos=f.index.searchsorted(decision,side='right')-1
            valid=pos>=0 and (decision-f.index[pos]).total_seconds()<=900
            parts.append(f.iloc[pos].to_dict() if valid else dict(direction=np.nan,slope=np.nan,momentum=np.nan))
        a,b=parts
        rows.append(dict(name=s['name'],decision=str(decision),side=s['side'],
            feature_close_m5=str(m5.index[m5.index.searchsorted(decision,side='right')-1])
                if m5.index.searchsorted(decision,side='right') else None,
            m5_direction=a['direction'],m5_slope=a['slope'],m5_momentum=a['momentum'],
            m15_direction=b['direction'],m15_slope=b['slope']))
    return [{key:(None if isinstance(value,float) and not np.isfinite(value) else value)
             for key,value in row.items()} for row in rows]


def masks(row):
    side=row['side']
    aligned5=row['m5_direction']==side and row['m5_slope']==side
    aligned15=row['m15_direction']==side and row['m15_slope']==side
    return dict(no_filter=True,trend_M5=aligned5,trend_M15=aligned15,
                trend_both=aligned5 and aligned15,
                trend_momentum_M5=aligned5 and row['m5_momentum']==side)


def completed_trade_metrics(trades):
    pnl=np.array([t['net_pnl_per_ounce'] for t in trades])
    equity=np.r_[0.,pnl.cumsum()]
    losses=-pnl[pnl<0].sum()
    return dict(trades=len(trades),net_pnl_per_ounce=float(pnl.sum()),
        expectancy_per_ounce=float(pnl.mean()) if len(pnl) else None,
        profit_factor=float(pnl[pnl>0].sum()/losses) if losses else None,
        max_closed_trade_drawdown_per_ounce=float((np.maximum.accumulate(equity)-equity).max()))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--objects',type=Path,required=True)
    p.add_argument('--ticks',type=Path,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--13x-buffers',dest='buffers_13x',type=Path,nargs='*',default=[])
    a=p.parse_args()
    ticks=pd.concat([pd.read_csv(f) for f in a.ticks],ignore_index=True).drop_duplicates().sort_values('time_msc',kind='stable')
    signals=signals_from_objects(a.objects)
    labels=classify(signals,ticks)
    cutoff=pd.Timestamp('2026-05-06')
    cutoff_ms=cutoff.value//1_000_000
    train_ticks=ticks[ticks.time_msc<cutoff_ms]
    results=[]
    for rule in masks(labels[0]):
        filtered=[s for s,row in zip(signals,labels) if masks(row)[rule]]
        train=simulate([s for s in filtered if s['decision']<cutoff],train_ticks)
        all_week=simulate(filtered,ticks)
        # Preserve state across cutoff: do not invent a flat portfolio and take
        # signals that a preceding open position would have blocked.
        validation_trades=[t for t in all_week['trades'] if pd.Timestamp(t['decision'])>=cutoff]
        validation=dict(trades=validation_trades,metrics=completed_trade_metrics(validation_trades),
            basis='Decision-date partition of continuous frozen-rule replay; positions carried across cutoff.')
        censored=sum(e['reason'].startswith('censored') for e in train['excluded'])
        eligible=(train['metrics']['trades']>=5 and train['metrics']['net_pnl_per_ounce']>0 and not censored)
        results.append(dict(rule=rule,signals=len(filtered),train=train,validation=validation,
                            descriptive_all_week=all_week,eligible_from_train=eligible))
    candidates=[r for r in results if r['eligible_from_train']]
    chosen=max(candidates,key=lambda r:r['train']['metrics']['expectancy_per_ounce'])['rule'] if candidates else None
    provisional=[]
    for path in a.buffers_13x:
        events=events_from_buffers(path)
        entry_signals=[]
        for e in events:
            for buffer,side in ((2,1),(3,-1)):
                if buffer in e['buffers']:
                    entry_signals.append(dict(name=f'{e["time"]}_{buffer}',decision=e['time'],side=side))
        event_labels=classify(entry_signals,ticks)
        for rule in ('no_filter','trend_M5','trend_M15','trend_both','trend_momentum_M5'):
            allowed={s['name'] for s,row in zip(entry_signals,event_labels) if masks(row)[rule]}
            gated=[]
            for e in events:
                buffers=set(e['buffers'])
                for buffer in (2,3):
                    if f'{e["time"]}_{buffer}' not in allowed:
                        buffers.discard(buffer)
                gated.append(dict(time=e['time'],buffers=buffers))
            replay=simulate_13x(gated,ticks)
            validation_trades=[t for t in replay['trades'] if pd.Timestamp(t['decision'])>=cutoff]
            provisional.append(dict(source=str(path.resolve()),rule=rule,replay=replay,
                validation_metrics=completed_trade_metrics(validation_trades),
                warning='13X entries remain provisional. Preserve original exit events when gating entries. No approval.'))
    payload=dict(results=results,signal_features=labels,selected_from_train=chosen,
        provisional_13x=provisional,
        classification='experimental_not_approved',method='Train May4-5 with truncated quotes; validation by decision date of continuous frozen-rule replay May6-8, positions not reset.',
        sources=[dict(path=str(f.resolve()),sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in [a.objects,*a.buffers_13x,*a.ticks]],
        warning='Previously examined dates, not untouched OOS. Small sample and multiple related tests. '
                'EMA5/20 M5 and EMA20/50 M15, slope3 bars; completed bars only. '
                'Warmup/missing features reject filtered entries. Quotes raw broker clock; no NY conversion. '
                'Censored trades excluded, risk incomplete. Costs hypotheses; no recommendation/real orders.')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(payload,indent=2,allow_nan=False,default=str),encoding='utf-8')
    print(json.dumps([dict(rule=r['rule'],train=r['train']['metrics'],validation=r['validation']['metrics'],
                           all_week=r['descriptive_all_week']['metrics'],eligible=r['eligible_from_train']) for r in results],indent=2))


if __name__=='__main__':
    main()
