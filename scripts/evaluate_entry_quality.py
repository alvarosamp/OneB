"""Replay a fixed net reward/risk gate on an original Gold object capture.

This is descriptive research on already-seen weeks, not untouched OOS proof.
No connection to a broker and no order API are used.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from backtest_original_gold_ticks import signals_from_objects, simulate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--objects', type=Path, required=True)
    parser.add_argument('--ticks', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--min-net-rr', type=float, default=1.0)
    args = parser.parse_args()
    signals = signals_from_objects(args.objects)
    ticks = pd.concat([pd.read_csv(p) for p in args.ticks], ignore_index=True)
    ticks = ticks.drop_duplicates().sort_values('time_msc', kind='stable')
    common = dict(latency_ms=250, slippage=.05, commission=.1, hold_hours=4,
                  max_gap_seconds=60)
    baseline = simulate(signals, ticks, **common)
    gated = simulate(signals, ticks, min_net_rr=args.min_net_rr, **common)
    sources = [args.objects, *args.ticks, Path(__file__),
               Path(__file__).with_name('entry_quality.py'),
               Path(__file__).with_name('backtest_original_gold_ticks.py')]
    report = dict(symbol='XAUUSD.s', timeframe='M10', signals=len(signals),
                  tick_rows=len(ticks), min_net_rr=args.min_net_rr,
                  threshold_status='posthoc_diagnostic_not_pre_registered_OOS',
                  baseline=baseline, gated=gated,
                  gated_exclusions=dict(Counter(x['reason'] for x in gated['excluded'])),
                  sources=[dict(path=str(p.resolve()),
                                sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                           for p in sources],
                  classification='experimental_not_approved',
                  warning='Only a manual advisory gate; no automatic orders. '
                  'Weeks already inspected, so improvement is not independent validation. '
                  'Censored positions have unknown PnL; commissions/slippage remain hypotheses. '
                  'Quote clock is raw MT5 time, not certified exchange time. '
                  'Do not optimize this threshold on these weeks or infer live edge.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False),
                           encoding='utf-8')
    print(json.dumps(dict(signals=len(signals),
                          baseline=baseline['metrics'], gated=gated['metrics'],
                          gated_exclusions=report['gated_exclusions']), indent=2))


if __name__ == '__main__':
    main()
