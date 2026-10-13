"""Compare logical rows, ignoring chart enumeration order, between tester modes."""
import argparse
import csv
import json
from pathlib import Path


def compare(left, right):
    def rows(path):
        with Path(path).open(encoding='utf-8-sig', newline='') as stream:
            return { (r['observed_at'], r['name']): r for r in csv.DictReader(stream, delimiter=';') }
    a, b = rows(left), rows(right)
    common = a.keys() & b.keys()
    different = [key for key in sorted(common) if a[key] != b[key]]
    fields = sorted(set().union(*(a[k].keys() for k in common))) if common else []
    field_changes = {f: sum(a[k].get(f) != b[k].get(f) for k in common) for f in fields}
    price_deltas = {}
    for field in ('price0', 'price1'):
        values = [abs(float(a[k][field])-float(b[k][field])) for k in common
                  if a[k].get(field) is not None and b[k].get(field) is not None]
        price_deltas[field] = max(values, default=0.0)
    return {'left': str(left), 'right': str(right), 'left_rows': len(a), 'right_rows': len(b),
            'only_left': len(a.keys()-b.keys()), 'only_right': len(b.keys()-a.keys()),
            'different_common_rows': len(different),
            'changed_fields': field_changes, 'maximum_absolute_price_difference': price_deltas,
            'examples': [{'key': k, 'left': a[k], 'right': b[k]} for k in different[:10]],
            'warning': 'Mode agreement is instrumentation evidence for this sample, not economic validation.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('left', type=Path)
    p.add_argument('right', type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = compare(args.left, args.right)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k != 'examples'}, ensure_ascii=False, indent=2))
