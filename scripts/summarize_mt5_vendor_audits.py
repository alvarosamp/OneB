"""Summarize original EX5 integrity tests. This is not an economic backtest."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def summarize(directory):
    rows = []
    for path in sorted(directory.glob('*_buffers.json')):
        buffer = json.loads(path.read_text(encoding='utf-8'))
        object_path = path.with_name(path.name.replace('_buffers.json', '_objects.json'))
        objects = json.loads(object_path.read_text(encoding='utf-8')) if object_path.exists() else {}
        raw = path.with_suffix('.csv')
        match = re.fullmatch(r'(.*)_([0-7])_(.+)_PERIOD_(.+)', path.stem.removesuffix('_buffers'))
        label = match[1] if match else ''
        config = Path(__file__).resolve().parents[1] / 'configs' / 'mt5' / (label+'.ini')
        config_text = config.read_text(encoding='utf-8-sig') if config.exists() else ''
        model = re.search(r'^Model=(\d+)', config_text, re.M)
        journal_path = directory / (label.removeprefix(directory.name+'_')+'.log')
        journal = journal_path.read_text(encoding='utf-8-sig', errors='replace') if journal_path.exists() else ''
        warnings = [line for line in journal.splitlines() if re.search(r'real ticks.*(absent|discarded|not found)|no real ticks', line, re.I)]
        rows.append({'case': path.stem.removesuffix('_buffers'),
                     'configured_model': int(model[1]) if model else None,
                     'real_tick_warnings': warnings[:10],
                     'first': buffer['first_observed'], 'last': buffer['last_observed'],
                     'observations': buffer['rows'], 'rechecks': buffer['rechecks'],
                     'unavailable': buffer['unavailable_rows'],
                     'buffer_revisions': buffer['closed_bar_buffer_changes'],
                     'unique_objects': objects.get('unique_objects'),
                     'object_field_revisions': objects.get('field_revisions'),
                     'gold_post_initial_candidates': objects.get('post_initial_gold_entries'),
                     'candidate_lags_seconds': objects.get('post_initial_entry_lag_seconds'),
                     'truncated_snapshots': objects.get('truncated_snapshots'),
                     'raw_buffer_sha256': hashlib.sha256(raw.read_bytes()).hexdigest()})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    rows = summarize(args.directory)
    models = sorted({row['configured_model'] for row in rows if row['configured_model'] is not None})
    report = {'classification': 'experimental', 'economic_ranking': None,
              'configured_models': models, 'cases': rows, 'warning': 'Small samples. Model 0 requests generated ticks; model 4 requests real ticks; inspect journal for fallback. No commissions, slippage or latency execution model; no profitability, paper trading or no-repaint approval.'}
    (args.directory / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# Auditoria dos originais MT5', '', f'Não é um backtest econômico. Modelos configurados: {models} (0=gerados, 4=reais solicitados). Sem otimização. Conferir fallback nos journals.', '',
             '| Caso | Observações | Rechecagens | Revisões de buffers | Indisponíveis | Objetos únicos | Entradas Gold após início |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        lines.append(f"| {row['case']} | {row['observations']} | {row['rechecks']} | {row['buffer_revisions']} | {row['unavailable']} | {row['unique_objects']} | {row['gold_post_initial_candidates']} |")
    lines += ['', 'Revisões de buffers auxiliares não provam repaint de entradas. Zero revisões não certifica ausência de repaint.',
              'Os períodos podem ser diferentes entre casos; primeiro/último horário e avisos de ticks estão no summary.json. Contagens não são ranking.',
              'Objetos presentes na primeira fotografia são histórico já preenchido e não são entradas causais.',
              'Para entradas, usar primeiro horário observado, nunca retroceder execução ao horário desenhado.',
              'Mudanças em texto de resultado não são lucro realizável. Não usar GAIN/LOSS para validar rentabilidade.',
              'Ranking econômico indisponível. Classificação: experimental; não aprovado para paper trading.']
    (args.directory / 'summary.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({'cases': len(rows), 'classification': 'experimental', 'report': str((args.directory / 'summary.md').resolve())}))


if __name__ == '__main__':
    main()
