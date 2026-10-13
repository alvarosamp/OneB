"""Frozen May18-22 Gold executable-entry gate check; no broker orders.

The registered JSON fixes the date, signal, costs and threshold. This script
refuses out-of-window input and reports both gate and unchanged baseline.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from backtest_original_gold_ticks import signals_from_objects, simulate


def verify_config(config):
    expected = dict(symbol='XAUUSD.s', timeframe='M10',
                    min_net_reward_to_risk=1.0, slippage_price_per_side=.05,
                    commission_roundtrip_per_ounce=.1, max_hold_hours=4,
                    max_quote_gap_seconds=60, prohibit_optimization=True)
    if any(config.get(key) != value for key, value in expected.items()):
        raise ValueError('Inputs differ from the registered entry-gate test')
    if (config.get('from_inclusive'), config.get('to_exclusive')) not in {
        ('2026-05-18', '2026-05-23'), ('2026-05-25', '2026-05-30')
    }:
        raise ValueError('Dates differ from the registered entry-gate weeks')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--objects', type=Path, required=True)
    parser.add_argument('--ticks', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    verify_config(config)
    start = pd.Timestamp(config['from_inclusive'])
    end = pd.Timestamp(config['to_exclusive'])
    signals = signals_from_objects(args.objects)
    if not signals or any(not start <= row['decision'] < end for row in signals):
        raise ValueError('Signals missing or outside registered week')
    ticks = pd.concat([pd.read_csv(path) for path in args.ticks], ignore_index=True)
    ticks = ticks.drop_duplicates().sort_values('time_msc', kind='stable')
    first_ms = start.value // 1_000_000
    last_ms = end.value // 1_000_000
    if ticks.empty or (ticks.time_msc < first_ms).any() or (ticks.time_msc >= last_ms).any():
        raise ValueError('Quotes missing or outside registered week')
    kwargs = dict(latency_ms=250, slippage=config['slippage_price_per_side'],
                  commission=config['commission_roundtrip_per_ounce'],
                  hold_hours=config['max_hold_hours'],
                  max_gap_seconds=config['max_quote_gap_seconds'])
    baseline = simulate(signals, ticks, **kwargs)
    gate = simulate(signals, ticks,
                    min_net_rr=config['min_net_reward_to_risk'], **kwargs)
    sources = [args.config, args.objects, *args.ticks, Path(__file__),
               Path(__file__).with_name('entry_quality.py'),
               Path(__file__).with_name('backtest_original_gold_ticks.py')]
    report = dict(config=config, signal_count=len(signals), tick_count=len(ticks),
                  baseline=baseline, gate=gate,
                  gate_exclusions=dict(Counter(x['reason'] for x in gate['excluded'])),
                  sources=[dict(path=str(path.resolve()),
                                sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                           for path in sources],
                  classification='experimental_not_approved',
                  warning='The threshold was selected after prior weeks. A single '
                  'new week cannot authorize recommendations. Source week may not '
                  'be untouched across the whole project. Costs are hypotheses; '
                  'censored PnL excluded; no automatic orders.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                      allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(signals=len(signals), ticks=len(ticks),
                          baseline=baseline['metrics'], gate=gate['metrics'],
                          gate_exclusions=report['gate_exclusions']), indent=2))


if __name__ == '__main__':
    main()
