"""Frozen verification of Gold trend gates on another original-indicator capture.

No selection, no optimization, no orders. Prior ticks are feature warmup only.
"""
import argparse
import hashlib
import json
from pathlib import Path
from collections import Counter
import pandas as pd
from gold_trend_regime_replay import classify, masks
from backtest_original_gold_ticks import signals_from_objects, simulate


def verify_features_config(config):
    expected=dict(m5_ema_fast=5,m5_ema_slow=20,m15_ema_fast=20,m15_ema_slow=50,slope_bars=3)
    if any(config.get(k)!=v for k,v in expected.items()):
        raise ValueError('Config does not match frozen feature implementation')
    if not config.get('no_optimization') or config.get('primary_rule')!='trend_both':
        raise ValueError('Not the registered frozen replication')


def breakdown(trades):
    out={}
    for column in ('day','side'):
        groups={}
        for t in trades:
            key=str(pd.Timestamp(t['decision']).date()) if column=='day' else ('buy' if t['side']==1 else 'sell')
            g=groups.setdefault(key,dict(trades=0,net_pnl_per_ounce=0.))
            g['trades']+=1
            g['net_pnl_per_ounce']+=t['net_pnl_per_ounce']
        out[column]=groups
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--objects',type=Path,required=True)
    p.add_argument('--ticks',type=Path,nargs='+',required=True)
    p.add_argument('--warmup',type=Path,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    cfg=json.loads(a.config.read_text(encoding='utf-8'))
    verify_features_config(cfg)
    start,end=pd.Timestamp(cfg['verification_from']),pd.Timestamp(cfg['verification_to_exclusive'])
    start_ms,end_ms=start.value//1_000_000,end.value//1_000_000
    raw=pd.concat([pd.read_csv(f) for f in a.ticks],ignore_index=True).drop_duplicates().sort_values('time_msc',kind='stable')
    if (raw.time_msc<start_ms).any() or (raw.time_msc>=end_ms).any():
        raise ValueError('Verification quotes outside registered interval')
    warmup=pd.concat([pd.read_csv(f) for f in a.warmup],ignore_index=True)
    if (warmup.time_msc>=start_ms).any():
        raise ValueError('Warmup includes verification/future quotes')
    combined=pd.concat([warmup,raw],ignore_index=True).drop_duplicates().sort_values('time_msc',kind='stable')
    signals=signals_from_objects(a.objects)
    if not signals or any(not start<=s['decision']<end for s in signals):
        raise ValueError('Signals absent or outside registered interval')
    labels=classify(signals,combined)
    results=[]
    for rule in (cfg['baseline'],cfg['primary_rule'],cfg['secondary_rule']):
        chosen=[s for s,row in zip(signals,labels) if masks(row)[rule]]
        for cost in cfg['cost_scenarios']:
            replay=simulate(chosen,raw,latency_ms=cfg['latency_ms'],slippage=cost['slippage'],
                commission=cost['commission'],hold_hours=cfg['hold_hours'],max_gap_seconds=cfg['max_quote_gap_seconds'])
            results.append(dict(rule=rule,signals_allowed=len(chosen),signals_rejected_by_rule=len(signals)-len(chosen),
                replay=replay,exclusion_counts=dict(Counter(r['reason'] for r in replay['excluded'])),
                breakdown=breakdown(replay['trades'])))
    primary=[r for r in results if r['rule']==cfg['primary_rule']]
    central=next(r for r in primary if r['replay']['assumptions']['slippage_price_per_side']==.05)
    cen=sum(v for k,v in central['exclusion_counts'].items() if k.startswith('censored'))
    # This is a descriptive replication outcome, never a paper-trading promotion.
    status='positive_but_insufficient' if central['replay']['metrics']['net_pnl_per_ounce']>0 and not cen else 'not_confirmed'
    sources=[a.config,a.objects,*a.ticks,*a.warmup,Path(__file__),
             Path(__file__).with_name('gold_trend_regime_replay.py'),Path(__file__).with_name('backtest_original_gold_ticks.py')]
    report=dict(registered_config=cfg,verification_signals=len(signals),verification_tick_rows=len(raw),
        warmup_tick_rows=len(warmup),results=results,signal_features=labels,
        primary_replication_outcome=status,classification='experimental_not_approved',
        sources=[dict(path=str(f.resolve()),sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in sources],
        warning='New week for this hypothesis, not proof of untouched data across the entire project. '
        'Prior warmup contains no current signals. No parameter/rule selection from verification. '
        'Few trades, related tests, costs hypotheses, censored PnL excluded and risk incomplete. '
        'No calibrated confidence or profit promise; no trades sent.')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(status=status,results=[dict(rule=r['rule'],assumptions=r['replay']['assumptions'],
        metrics=r['replay']['metrics'],exclusions=r['exclusion_counts']) for r in results]),indent=2))


if __name__=='__main__':
    main()
