"""Conservative development audit; no automatic promotion or profitability claim."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from vendor_strategy_backtest import bh
from walkforward_execution_research import score


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    args=p.parse_args()
    report=json.loads((args.directory/'results.json').read_text(encoding='utf-8'))
    rows, hours, sides=[],[],[]
    rng=np.random.default_rng(20260927)
    for row in report['results']:
        for variant in ('unfiltered','filtered'):
            key='trades' if variant=='unfiltered' else 'filtered_trades'
            trades=[t for fold in row['folds'] for t in fold[key]]
            m=score(trades)
            for side in (-1,1):
                sides.append(dict(symbol=row['symbol'],family=row['family'],minutes=row['minutes'],
                    variant=variant,side='buy' if side==1 else 'sell',
                    **score([t for t in trades if t['side']==side])))
            frame=pd.DataFrame([t for t in trades if t['net'] is not None])
            # Include zero-trade weekdays in validation; 5-day moving blocks
            # preserve short-term dependence better than independent trade t-tests.
            start=pd.Timestamp(row['folds'][0]['train_end']).normalize()
            end=pd.Timestamp(row['folds'][-1]['validation_end']).normalize()
            calendar=pd.date_range(start,end-pd.Timedelta(days=1),freq='B')
            daily=(frame.groupby('date').net.sum().reindex(calendar.strftime('%Y-%m-%d'),fill_value=0).to_numpy()
                   if len(frame) else np.zeros(len(calendar)))
            pvalue, lower=None,None
            if len(daily)>=20 and m['trades']>=30:
                starts=rng.integers(0,len(daily)-4,size=(1000,int(np.ceil(len(daily)/5))))
                indices=(starts[:,:,None]+np.arange(5)).reshape(1000,-1)[:,:len(daily)]
                means=daily[indices].mean(axis=1)
                lower=float(np.quantile(means,.025))
                centered=daily-daily.mean()
                pvalue=float((1+(centered[indices].mean(axis=1)>=daily.mean()).sum())/1001)
            rows.append(dict(symbol=row['symbol'],family=row['family'],minutes=row['minutes'],variant=variant,
                **m,positive_folds=sum((f[variant]['expectancy'] or 0)>0 for f in row['folds']),
                block_bootstrap_p=pvalue,lower_daily_pnl_95=lower,
                status='needs_more_data' if m['trades']<100 or m['censored'] else 'experimental'))
            for fold in row['folds']:
                for hour,metric in fold['by_hour'].items():
                    hours.append(dict(symbol=row['symbol'],family=row['family'],minutes=row['minutes'],
                        fold=fold['fold'],ny_hour_bin=hour,**metric))
    table=pd.DataFrame(rows)
    table['bh_q']=bh(table.block_bootstrap_p)
    table['robust_development_candidate']=((table.positive_folds==3)&(table.trades>=100)&
        (table.censored==0)&(table.lower_daily_pnl_95>0)&(table.bh_q<.05))
    table.to_csv(args.directory/'development_summary.csv',index=False)
    pd.DataFrame(hours).to_csv(args.directory/'hours_descriptive.csv',index=False)
    pd.DataFrame(sides).to_csv(args.directory/'sides_descriptive.csv',index=False)
    selected=table[table.robust_development_candidate]
    text=['# Desenvolvimento walk-forward por timeframe e horário','',
          'Resultados de hipóteses aproximadas, NÃO dos EX5. Nenhum aprovado para paper trading.',
          f'{len(report["results"])} combinações; {len(table)} comparações base/filtrada; três folds.',
          '20% finais permanecem sem avaliação econômica. Gold com spread sintético; Nasdaq bid/ask externo.',
          'Bootstrap em blocos de cinco dias, 1.000 réplicas; BH entre comparações. '
          'Não cobre todo o histórico de testes do projeto, nem certifica significância sob todas as dependências.',
          f'Candidatos que passam o filtro conservador de desenvolvimento: {len(selected)}.', '',
          'Filtro: >=100 trades, zero censura, três folds positivos, limite inferior diário >0 e q<0,05.',
          'Não completar custos nem resolver mapeamento do original implica permanecer experimental.', '',
          'Ver development_summary.csv, hours_descriptive.csv e results.json para dados completos.']
    (args.directory/'summary.md').write_text('\n'.join(text),encoding='utf-8')
    print(table[['symbol','family','minutes','variant','trades','net','positive_folds','censored','bh_q','robust_development_candidate']].to_string(index=False))


if __name__=='__main__':
    main()
