"""Read-only broker coverage probe. Never sends orders or requests credentials."""
import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

from export_mt5_intraday import export_rates, symbol_spec


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--terminal', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--symbol', action='append')
    p.add_argument('--probe-date', action='append')
    p.add_argument('--rates-only', action='store_true')
    p.add_argument('--skip-rates', action='store_true')
    p.add_argument('--probe-hour', type=int, default=16, choices=range(24))
    p.add_argument('--probe-hours', type=int, default=1, choices=range(1, 25))
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if not mt5.initialize(path=args.terminal, timeout=60000):
        raise RuntimeError(mt5.last_error())
    report = {'generated_at': datetime.now(timezone.utc).isoformat(), 'symbols': [],
              'warning': 'Raw broker timestamps; UTC offset not historically certified. No orders. No commission assumption.'}
    try:
        terminal = mt5.terminal_info()
        if not terminal or not terminal.connected:
            raise RuntimeError('Authenticated broker connection unavailable')
        names = [s.name for s in mt5.symbols_get() or [] if any(
            term in s.name.upper() for term in ('XAU', 'US100', 'NQ', 'GC.', 'WIN', 'USTEC', 'NAS'))]
        report['available_matching_symbols'] = names
        if args.symbol:
            names = [name for name in names if name in args.symbol]
        for name in names:
            if not mt5.symbol_select(name, True):
                continue
            item = {'symbol': name, 'specification': symbol_spec(name), 'tick_probes': []}
            report['symbols'].append(item)
            try:
                if args.skip_rates:
                    raise RuntimeError('Rates intentionally skipped; see separate rates-only manifest')
                rates = export_rates(name, 'M1', datetime(2021, 1, 1, tzinfo=timezone.utc), datetime.now(timezone.utc))
                dest = args.output / f'{name}_M1.csv.gz'
                rates.to_csv(dest, index=False, compression='gzip')
                item['rates'] = {'rows': len(rates), 'sessions': rates.timestamp.dt.date.nunique(),
                    'first': str(rates.timestamp.min()), 'last': str(rates.timestamp.max()),
                    'path': str(dest.resolve()), 'sha256': hashlib.sha256(dest.read_bytes()).hexdigest()}
            except Exception as exc:
                item['rates_error'] = str(exc)
            (args.output / 'coverage.json').write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
            print(json.dumps({'symbol': name, 'rates': item.get('rates'), 'rates_error': item.get('rates_error')}, default=str), flush=True)
            # Bounded one-hour windows establish retention, not full coverage.
            for date in ([] if args.rates_only else args.probe_date or ['2026-09-25', '2026-05-04', '2026-04-20', '2023-09-20', '2021-09-20']):
                start = datetime.fromisoformat(date+f'T{args.probe_hour:02d}:00:00+00:00')
                print(json.dumps({'requesting_ticks': name, 'date': date}), flush=True)
                values = mt5.copy_ticks_range(name, start, start+timedelta(hours=args.probe_hours), mt5.COPY_TICKS_INFO)
                probe = {'requested_start': start.isoformat(), 'requested_hours': args.probe_hours,
                         'rows': 0 if values is None else len(values), 'last_error': mt5.last_error()}
                item['tick_probes'].append(probe)
                if values is not None and len(values):
                    frame = pd.DataFrame(values)
                    valid = (frame.bid > 0) & (frame.ask >= frame.bid)
                    probe.update({'valid_quotes': int(valid.sum()), 'first_time_msc': int(frame.time_msc.min()),
                        'last_time_msc': int(frame.time_msc.max()),
                        'median_spread_price': float((frame.ask-frame.bid)[valid].median()) if valid.any() else None})
                    dest = args.output / f'{name}_ticks_{date}_{args.probe_hour:02d}h_{args.probe_hours}hours.csv.gz'
                    frame.to_csv(dest, index=False, compression='gzip')
                    probe['path'] = str(dest.resolve())
                    probe['sha256'] = hashlib.sha256(dest.read_bytes()).hexdigest()
                (args.output / 'coverage.json').write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
            (args.output / 'coverage.json').write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
            print(json.dumps(item, ensure_ascii=False, default=str), flush=True)
    finally:
        mt5.shutdown()


if __name__ == '__main__':
    main()
