"""Descriptive day/hour/direction breakdown: never selects a profitable bin."""
import argparse
import json
from pathlib import Path
from collections import Counter
import pandas as pd


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('reports',type=Path,nargs='+')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    rows=[]
    for path in a.reports:
        report=json.loads(path.read_text(encoding='utf-8'))
        scenario=next(r for r in report['scenarios'] if r['assumptions']['latency_ms']==250 and
                      r['assumptions']['slippage_price_per_side']==.05)
        trades=pd.DataFrame(scenario['trades'])
        trades['raw_date']=pd.to_datetime(trades.decision).dt.strftime('%Y-%m-%d')
        trades['raw_hour_bin']=pd.to_datetime(trades.decision).dt.hour//4*4
        breakdown={}
        for column in ('raw_date','raw_hour_bin','side'):
            breakdown[column]={str(key):dict(trades=len(group),net_pnl_per_ounce=float(group.net_pnl_per_ounce.sum()))
                               for key,group in trades.groupby(column)}
        rows.append(dict(source=str(path.resolve()),metrics=scenario['metrics'],breakdown=breakdown,
            exclusions=dict(Counter(r['reason'] for r in scenario['excluded'])),
            classification='experimental_not_approved'))
    a.output.write_text(json.dumps(dict(results=rows,warning='Descriptive only, tiny overlapping sample. '
        'Hours are raw MT5 server domain, not historically certified NY/London sessions. '
        'No hour selected on these results. Censored PnL omitted; risk incomplete. '
        '13X entry mapping provisional.'),indent=2),encoding='utf-8')
    print(json.dumps(rows,indent=2))


if __name__=='__main__':
    main()
