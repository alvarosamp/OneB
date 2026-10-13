"""Frozen rule hypotheses, sequential validation and hour filters selected only in train.

NOT purchased EX5 results. No paper-trading promotion. No orders.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from vendor_strategy_backtest import (features, signal_13x, signal_100_pips,
    signal_duck, signal_gold_fakeout, signal_london_box, signal_gap_drive)


def aggregate(raw, minutes):
    rules = {'volume':'sum'}
    for prefix in ('', 'bid_', 'ask_'):
        rules.update({prefix+'open':'first', prefix+'high':'max', prefix+'low':'min', prefix+'close':'last'})
    bars = raw.resample(f'{minutes}min').agg(rules)
    count = raw.close.resample(f'{minutes}min').count()
    # Do not use partial candles as completed higher-timeframe observations.
    return bars[count == minutes//5].dropna()


def simulate(f, signal, minutes, start, end, fixed=False, slippage=.1, commission=.2):
    trades, next_index = [], 0
    deadline_delta = pd.Timedelta(hours=4)
    values = signal.to_numpy()
    quotes = {column:f[column].to_numpy() for column in f.columns if column.startswith(('bid_','ask_'))}
    atr = f.atr.to_numpy()
    for i in np.flatnonzero(values):
        if i < next_index or i+1 >= len(f):
            continue
        decision = f.index[i]+pd.Timedelta(minutes=minutes)
        if not start <= decision < end or f.index[i+1] != decision:
            continue
        side, k = int(values[i]), i+1
        entry = float(quotes['ask_open' if side == 1 else 'bid_open'][k])+side*slippage
        risk = 20. if fixed else float(atr[i])
        if not np.isfinite(risk) or risk <= 0:
            continue
        reward = 15. if fixed else 1.5*risk
        stop, target = entry-side*risk, entry+side*reward
        exit_price, reason, j = None, 'censored', k
        deadline = min(decision+deadline_delta, end)
        prefix = 'bid_' if side == 1 else 'ask_'
        for j in range(k, len(f)):
            if f.index[j]+pd.Timedelta(minutes=minutes) > deadline:
                break
            if j > k and f.index[j]-f.index[j-1] != pd.Timedelta(minutes=minutes):
                break
            adverse = quotes[prefix+'low' if side == 1 else prefix+'high'][j]
            favorable = quotes[prefix+'high' if side == 1 else prefix+'low'][j]
            if side*(adverse-stop) <= 0:
                # Conservative stop-first when both levels lie within one candle;
                # gap through stop uses the worse executable opening quote.
                opening = quotes[prefix+'open'][j]
                exit_price = min(stop, opening) if side == 1 else max(stop, opening)
                reason = 'stop'
            elif side*(favorable-target) >= 0:
                exit_price, reason = target, 'target'
            elif f.index[j]+pd.Timedelta(minutes=minutes) == deadline:
                exit_price, reason = quotes[prefix+'close'][j], 'time'
            if exit_price is not None:
                break
        next_index = j+1
        if exit_price is None:
            trades.append(dict(decision=str(decision), date=str(decision.date()), hour=decision.tz_convert('America/New_York').hour,
                side=side, net=None, reason='censored'))
        else:
            trades.append(dict(decision=str(decision), date=str(decision.date()), hour=decision.tz_convert('America/New_York').hour,
                side=side, net=float(side*(exit_price-side*slippage-entry)-commission), reason=reason))
    return trades


def score(trades):
    p = np.array([t['net'] for t in trades if t['net'] is not None])
    equity = np.r_[0., p.cumsum()]
    loss = -p[p < 0].sum()
    return dict(trades=len(p), censored=sum(t['net'] is None for t in trades), net=float(p.sum()),
        expectancy=float(p.mean()) if len(p) else None,
        profit_factor=float(p[p > 0].sum()/loss) if loss else None,
        drawdown_closed=float((np.maximum.accumulate(equity)-equity).max()))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--nasdaq', type=Path, required=True)
    p.add_argument('--gold', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results, manifest = [], []
    for symbol, path in (('NAS100_CFD', args.nasdaq), ('XAUUSD_proxy', args.gold)):
        raw = pd.read_csv(path)
        raw.index = pd.to_datetime(raw.pop('timestamp'), utc=True)
        if not raw.index.is_monotonic_increasing or raw.index.has_duplicates:
            raise ValueError('Invalid chronology')
        synthetic = 'bid_open' not in raw
        if synthetic:
            # Explicit fixed-spread hypothesis, not observed broker costs.
            for field in ('open','high','low','close'):
                raw['bid_'+field] = raw[field]
                raw['ask_'+field] = raw[field]+.30
        if 'volume' not in raw:
            raw['volume'] = 0
        manifest.append(dict(symbol=symbol, source=str(path.resolve()), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                             quotes='synthetic spread 0.30' if synthetic else 'paired external bid/ask'))
        days = pd.DatetimeIndex(raw.index.normalize().unique())
        # First 50% only starts development, next 30% three expanding folds,
        # last 20% sealed: never evaluate it in this program.
        cuts = [days[int(len(days)*q)] for q in (.5,.6,.7,.8)]
        for minutes in (5,10,15,30,60):
            f = features(aggregate(raw, minutes))
            # Correct documented 100 Pips variant: RSI10 on median price, not RSI14 close.
            delta = ((f.high+f.low)/2).diff()
            up = delta.clip(lower=0).ewm(alpha=.1, adjust=False, min_periods=10).mean()
            down = -delta.clip(upper=0).ewm(alpha=.1, adjust=False, min_periods=10).mean()
            f['rsi'] = (100-100/(1+up/down)).where((up+down) != 0, 50)
            params = dict(adx=20, ma='ema', sync=0, separation=0., touch_atr=0., window='crazy_24_7',
                          end_hour_ny=3, box_hours=3, buffer_atr=0., hour_ny=9.5, direction='first_bar')
            functions = [('13x_hypothesis',signal_13x),('100pips_hypothesis',signal_100_pips),('duck_hypothesis',signal_duck)]
            if synthetic:
                functions += [('gold_hypothesis',signal_gold_fakeout),('london_hypothesis',signal_london_box)]
            else:
                functions += [('gap_OHLC_proxy',signal_gap_drive)]
            functions += [('ema13_baseline',lambda x,p: np.sign(x.close-x.ema13).fillna(0))]
            for family, fn in functions:
                sig = fn(f, params)
                slippage, commission = (.05,.1) if synthetic else (.25,.5)
                folds = []
                for fold in range(3):
                    train = simulate(f,sig,minutes,days[0],cuts[fold],family=='gold_hypothesis',slippage,commission)
                    # Disjoint 4h NY bins; only train can activate a bin, >=30 completed trades.
                    selected = []
                    for h in range(0,24,4):
                        m = score([t for t in train if h <= t['hour'] < h+4])
                        if m['trades'] >= 30 and m['expectancy'] > 0:
                            selected.append(h)
                    hours = (f.index+pd.Timedelta(minutes=minutes)).tz_convert('America/New_York').hour
                    mask = np.array([int(h)//4*4 in selected for h in hours])
                    base = simulate(f,sig,minutes,cuts[fold],cuts[fold+1],family=='gold_hypothesis',slippage,commission)
                    filtered = simulate(f,sig.where(mask,0),minutes,cuts[fold],cuts[fold+1],family=='gold_hypothesis',slippage,commission)
                    folds.append(dict(fold=fold, train_end=str(cuts[fold]), validation_end=str(cuts[fold+1]),
                        selected_hour_bins=selected, unfiltered=score(base), filtered=score(filtered),
                        by_hour={str(h):score([t for t in base if h<=t['hour']<h+4]) for h in range(0,24,4)},
                        trades=base, filtered_trades=filtered))
                results.append(dict(symbol=symbol, family=family, minutes=minutes, folds=folds,
                    positive_filtered_folds=sum((r['filtered']['expectancy'] or 0)>0 for r in folds),
                    classification='experimental', sealed_start=str(cuts[-1])))
            print(f'DONE {symbol} M{minutes}', flush=True)
    report = dict(sources=manifest, results=results, method='Frozen hypotheses, 3 expanding folds; 20% sealed and unread economically.',
        warning='Not EX5 performance. Correlated multiple tests: do not select winner by raw PF. '
        'No significance or calibrated probability claimed. Censored trades excluded from PnL; inspect count. '
        'No swap/real exit latency. Gold synthetic spread. All units price per unit, not account returns.')
    (args.output/'results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
