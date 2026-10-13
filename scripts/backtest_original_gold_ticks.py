"""Executable, delayed first-observation Gold pilot; not a proprietary rule replica.

All timestamps stay in the common raw MT5 domain (not converted to a session TZ).
One position at a time; absolute vendor levels frozen at first availability.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from entry_quality import assess_entry


def signals_from_objects(path):
    frame = pd.read_csv(path, sep=';', keep_default_na=False)
    frame['observed'] = pd.to_datetime(frame.observed_at, format='%Y.%m.%d %H:%M:%S')
    if not frame.observed.is_monotonic_increasing:
        raise ValueError('Nonchronological snapshots')
    if (frame.text == 'TRUNCATED').any():
        raise ValueError('Truncated capture')
    initial = frame.observed.iloc[0]
    seen, signals = set(), []
    for observed, snapshot in frame.groupby('observed', sort=False):
        objects = snapshot.set_index('name')
        for name in snapshot.name:
            match = re.fullmatch(r'(GFC_\d+_(B|S))_e', name)
            if not match or name in seen:
                continue
            seen.add(name)
            if observed == initial:
                continue
            prefix, side = match.groups()
            if prefix+'_sl' not in objects.index or prefix+'_tp' not in objects.index:
                raise ValueError('Levels unavailable at first observation')
            signals.append(dict(name=name, decision=observed, side=1 if side == 'B' else -1,
                stop=float(objects.loc[prefix+'_sl', 'price0']),
                target=float(objects.loc[prefix+'_tp', 'price0'])))
    return signals


def simulate(signals, ticks, latency_ms=250, slippage=0.05, commission=0.1,
             hold_hours=4, max_gap_seconds=60, min_net_rr=None):
    if latency_ms < 0 or slippage < 0 or commission < 0 or hold_hours <= 0:
        raise ValueError('Invalid execution assumptions')
    if min_net_rr is not None and (not np.isfinite(min_net_rr) or min_net_rr < 0):
        raise ValueError('Invalid pre-entry reward/risk threshold')
    times = ticks.time_msc.to_numpy(dtype=np.int64)
    bid, ask = ticks.bid.to_numpy(float), ticks.ask.to_numpy(float)
    if len(times) == 0 or np.any(np.diff(times) < 0):
        raise ValueError('Empty or unordered ticks')
    if not (np.isfinite(bid).all() and np.isfinite(ask).all() and
            (bid > 0).all() and (ask >= bid).all()):
        raise ValueError('Invalid executable quotes')
    trades, excluded, busy_until = [], [], -1
    realized, equity_peak, mtm_drawdown = 0., 0., 0.
    for signal in signals:
        decision = int(signal['decision'].value // 1_000_000)
        if decision <= busy_until:
            excluded.append(dict(name=signal['name'], reason='position_open'))
            continue
        i = int(np.searchsorted(times, decision+latency_ms))
        if i == len(times) or times[i]-(decision+latency_ms) > 5000:
            excluded.append(dict(name=signal['name'], reason='no_timely_entry_quote'))
            continue
        side = signal['side']
        entry = (ask[i] if side == 1 else bid[i]) + side*slippage
        quality = assess_entry(side, bid[i], ask[i], signal['stop'], signal['target'],
                               slippage, commission, min_net_rr or 0)
        if quality['reason'] == 'levels_already_crossed':
            excluded.append(dict(name=signal['name'], reason='levels_already_crossed'))
            continue
        if min_net_rr is not None and not quality['allow']:
            excluded.append(dict(name=signal['name'], reason=quality['reason'],
                                 net_reward_to_risk=quality['net_reward_to_risk']))
            continue
        deadline = times[i] + int(hold_hours*3600000)
        end = min(int(np.searchsorted(times, deadline, side='left')), len(times)-1)
        exit_index, reason = None, 'censored_end_of_data'
        for j in range(i, end+1):
            if j > i and times[j]-times[j-1] > max_gap_seconds*1000:
                reason = 'censored_quote_gap'
                break
            mark = bid[j] if side == 1 else ask[j]
            if side*(mark-signal['stop']) <= 0:
                exit_index, reason = j, 'stop'
                break
            if side*(mark-signal['target']) >= 0:
                exit_index, reason = j, 'target'
                break
            if times[j] >= deadline:
                exit_index, reason = j, 'time_stop'
                break
        if exit_index is None:
            excluded.append(dict(name=signal['name'], reason=reason))
            # Unknown exit: do not silently assume position closed and take more signals.
            busy_until = times[end] if reason == 'censored_end_of_data' else deadline
            continue
        j = exit_index
        exit_price = (bid[j] if side == 1 else ask[j]) - side*slippage
        gross = side*(exit_price-entry)
        marks = (bid[i:j+1] if side == 1 else ask[i:j+1])-side*slippage
        path_pnl = side*(marks-entry)-commission
        equity_path = realized+path_pnl
        peaks = np.maximum.accumulate(np.r_[equity_peak,equity_path])[1:]
        mtm_drawdown = max(mtm_drawdown,float((peaks-equity_path).max()))
        equity_peak = max(equity_peak,float(equity_path.max()))
        realized += gross-commission
        trades.append(dict(name=signal['name'], decision=str(signal['decision']), side=side,
            entry_time_msc=int(times[i]), exit_time_msc=int(times[j]), entry=entry,
            exit=exit_price, stop=signal['stop'], target=signal['target'], reason=reason,
            entry_quality=quality,
            gross_pnl_per_ounce=gross, net_pnl_per_ounce=gross-commission,
            maximum_adverse_pnl_per_ounce=float(path_pnl.min()),
            maximum_favorable_pnl_per_ounce=float(path_pnl.max())))
        busy_until = times[j]
    pnl = np.array([t['net_pnl_per_ounce'] for t in trades])
    equity = np.r_[0., pnl.cumsum()]
    wins, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    return dict(assumptions=dict(latency_ms=latency_ms, slippage_price_per_side=slippage,
        commission_roundtrip_per_ounce=commission, hold_hours=hold_hours,
        max_quote_gap_seconds=max_gap_seconds, min_net_rr=min_net_rr), trades=trades, excluded=excluded,
        metrics=dict(trades=len(trades), net_pnl_per_ounce=float(pnl.sum()),
        expectancy_per_ounce=float(pnl.mean()) if len(pnl) else None,
        win_rate=float((pnl > 0).mean()) if len(pnl) else None,
        profit_factor=float(wins/losses) if losses else None,
        max_closed_trade_drawdown_per_ounce=float((np.maximum.accumulate(equity)-equity).max()),
        mark_to_market_drawdown_per_ounce=mtm_drawdown,
        risk_metrics_exclude_censored_positions=True,
        sharpe=None, sortino=None), classification='experimental')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--objects', type=Path, required=True)
    p.add_argument('--ticks', type=Path, nargs='+', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    ticks = pd.concat([pd.read_csv(f) for f in args.ticks], ignore_index=True)
    # Adjacent download windows can share a boundary quote. Remove exact duplicates only.
    ticks = ticks.drop_duplicates().sort_values('time_msc', kind='stable')
    signals = signals_from_objects(args.objects)
    results = [simulate(signals, ticks, latency, slip, commission)
        for latency in (0, 250, 1000) for slip, commission in ((0, 0), (.05, .1), (.15, .3))]
    report = dict(signals=len(signals), tick_rows=len(ticks), scenarios=results,
        sources=[dict(path=str(f.resolve()), sha256=hashlib.sha256(f.read_bytes()).hexdigest())
                 for f in [args.objects, *args.ticks]],
        warning='Short technical pilot, not OOS or optimized. Costs are hypotheses. '
        'No universal repaint certification. Closed-trade drawdown excludes intratrade risk. '
        'No annualized Sharpe or approval from such a short sample. Quotes match broker raw timestamp domain.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps([dict(assumptions=r['assumptions'], metrics=r['metrics'], excluded=len(r['excluded']))
                      for r in results], indent=2))


if __name__ == '__main__':
    main()
