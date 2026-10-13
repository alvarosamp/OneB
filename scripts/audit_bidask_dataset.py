"""Audit paired bid/ask bars without turning CFD quotes into futures evidence."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import pandas as pd
import numpy as np


def audit(path):
    frame = pd.read_csv(path)
    timestamp = pd.to_datetime(frame['timestamp'], utc=True, errors='coerce')
    report = {'path': str(Path(path).resolve()), 'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
              'rows': len(frame), 'invalid_timestamps': int(timestamp.isna().sum()),
              'duplicate_timestamps': int(timestamp.duplicated().sum()),
              'chronological': bool(timestamp.is_monotonic_increasing),
              'first': str(timestamp.min()), 'last': str(timestamp.max()),
              'days_with_bars': int(timestamp.dt.date.nunique()),
              'by_year': {}, 'ohlc_invalid': {}, 'quotes_missing': 0}
    required = [f'{side}_{field}' for side in ('bid', 'ask') for field in ('open', 'high', 'low', 'close')]
    missing = [c for c in required if c not in frame]
    if missing:
        raise ValueError(f'Missing columns: {missing}')
    report['quotes_missing'] = int(frame[required].isna().any(axis=1).sum())
    report['nonfinite_quotes'] = int((~np.isfinite(frame[required].to_numpy(dtype=float))).any(axis=1).sum())
    # Explicit proxy, not a certified exchange calendar: Sunday evening belongs
    # to Monday's overnight session. Calendar arithmetic avoids 24h DST errors.
    ny = timestamp.dt.tz_convert('America/New_York').dt.tz_localize(None)
    session_proxy = ny.dt.normalize() + pd.to_timedelta((ny.dt.hour >= 18).astype(int), unit='D')
    weekday = session_proxy.dt.dayofweek < 5
    report['overnight_session_proxy'] = {
        'convention': 'New York calendar date, rolling >=18:00 into next date; weekdays only; not exchange-calendar certified',
        'count': int(session_proxy[weekday].nunique()),
        'weekend_labels': int(session_proxy[~weekday].nunique()),
        'minimum_bars': int(session_proxy[weekday].value_counts().min()) if weekday.any() else 0}
    for side in ('bid', 'ask'):
        o, h, l, c = [frame[f'{side}_{field}'] for field in ('open', 'high', 'low', 'close')]
        report['ohlc_invalid'][side] = int(((h < pd.concat([o, l, c], axis=1).max(axis=1)) |
            (l > pd.concat([o, h, c], axis=1).min(axis=1)) | (frame[[f'{side}_{f}' for f in ('open','high','low','close')]] <= 0).any(axis=1)).sum())
    report['spread'] = {}
    for field in ('open', 'close'):
        spread = frame[f'ask_{field}']-frame[f'bid_{field}']
        report['spread'][field] = {'negative': int((spread < 0).sum()), 'zero': int((spread == 0).sum()),
                                  'median': float(spread.median()) if math.isfinite(spread.median()) else None,
                                  'p95': float(spread.quantile(.95)) if math.isfinite(spread.quantile(.95)) else None}
    for year in sorted(timestamp.dt.year.dropna().unique()):
        dates = timestamp[timestamp.dt.year == year]
        report['by_year'][str(int(year))] = {'rows': len(dates), 'days_with_bars': int(dates.dt.date.nunique())}
    report['integrity_pass'] = (len(frame) > 0 and report['invalid_timestamps'] == report['duplicate_timestamps'] == report['quotes_missing'] == report['nonfinite_quotes'] == 0
        and report['chronological'] and not any(report['ohlc_invalid'].values())
        and all(v['negative'] == 0 for v in report['spread'].values()))
    report['warning'] = ('Bars are not tick sequencing. Bid and ask OHLC extrema need not be simultaneous. '
        'Averaged mid OHLC is an approximation, not the observed midpoint path. '
        'Days with bars include partial days; no exchange-session calendar certification. '
        'Passing integrity is not profitability or broker-execution validation.')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.path)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
