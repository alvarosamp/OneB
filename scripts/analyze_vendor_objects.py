"""Audit first availability of vendor chart objects; never infer returns from labels."""
import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


def analyze(path):
    first = {}
    last = {}
    revisions = Counter()
    snapshots = truncated = 0
    initial = None
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream, delimiter=';'):
            observed = row['observed_at']
            initial = initial or observed
            if row['name'] == '__snapshot__':
                snapshots += 1
                truncated += row['text'] == 'TRUNCATED'
                continue
            name = row['name']
            if name not in first:
                first[name] = row.copy()
            if name in last:
                old = last[name]
                if observed < old['observed_at']:
                    raise ValueError('Nonchronological object observations')
                for field in ('time0', 'price0', 'time1', 'price1', 'text'):
                    if old[field] != row[field]:
                        revisions[field] += 1
            last[name] = row
    candidates = []
    for name, row in first.items():
        match = re.fullmatch(r'GFC_(\d+)_(B|S)_e', name)
        if not match:
            continue
        lag = (datetime.strptime(row['observed_at'], '%Y.%m.%d %H:%M:%S') -
               datetime.strptime(row['time0'], '%Y.%m.%d %H:%M:%S')).total_seconds()
        candidates.append({'name': name, 'direction': 'buy' if match[2] == 'B' else 'sell',
                           'drawn_at': row['time0'], 'first_seen': row['observed_at'],
                           'price': float(row['price0']), 'lag_seconds': lag,
                           'seeded_at_initial_snapshot': row['observed_at'] == initial})
    active = [r for r in candidates if not r['seeded_at_initial_snapshot']]
    return {'source': str(Path(path).resolve()), 'initial_observation': initial,
            'snapshots': snapshots, 'truncated_snapshots': truncated,
            'unique_objects': len(first), 'object_types': dict(Counter(r['type'] for r in first.values())),
            'field_revisions': dict(revisions), 'gold_entry_candidates': candidates,
            'post_initial_gold_entries': len(active),
            'post_initial_entry_lag_seconds': dict(Counter(r['lag_seconds'] for r in active)),
            'object_examples': list(first.values())[:25], 'classification': 'experimental',
            'warning': 'First_seen is availability, not drawn_at. Initial historical objects and GAIN/LOSS labels are not executable historical trades. No economic advantage inferred. Nonvisual object behavior still needs visual cross-check.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('objects', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = analyze(args.objects)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('gold_entry_candidates','object_examples')}, indent=2))
