"""Profile first available closed-bar values without assigning undocumented semantics."""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    frame = pd.read_csv(args.source, sep=';')
    frame = frame[frame['shift'] == 1].copy()
    rows = []
    for buffer, group in frame.groupby('buffer'):
        values = group.loc[group.status == 'ok', 'value']
        rows.append(dict(buffer=int(buffer), observations=len(group), nonempty=len(values),
            min=float(values.min()) if len(values) else None,
            max=float(values.max()) if len(values) else None,
            distinct=int(values.nunique()), common_values={str(k): int(v) for k,v in values.value_counts().head(8).items()},
            examples=group[group.status == 'ok'][['observed_at', 'bar_time', 'value']].head(8).to_dict('records')))
    report = dict(source=str(args.source.resolve()), sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
        buffers=rows, classification='experimental',
        warning='Numeric shape is not semantic mapping. Confirm plots/arrows against the original before trading.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    main()
