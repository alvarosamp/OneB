# Technical Edge Score (research)

## Purpose

`Technical Edge Score` ranks a chosen group of US equities for **observation
over the next five trading days**. It is not a buy/sell signal, a price target,
or an automated strategy.

The score is relative: an asset with `OBSERVAR` is stronger only compared with
the other assets in the same request. Do not compare scores from different
universes.

## Inputs

The current score equally averages the cross-sectional percentile of eight
features. Direction comes from the two-year, daily-candle research audit on
24 large-cap Nasdaq/US symbols, evaluated at a five-day horizon:

| Input | Reading in the audited sample |
| --- | --- |
| ADX(14), annualized volatility, EMA20/EMA50 gap | Higher ranks were favorable. |
| 5-day return, 5v20 momentum acceleration, 5-day return vs QQQ | Higher ranks tended to mean-revert. |
| MACD histogram 3-day slope, distance from prior 20-day high | Higher ranks also tended to mean-revert. |

This is why the score does not implement a simplistic “breakout = buy” rule.

## Guardrails and validation

- Candles are daily adjusted OHLCV; QQQ is the benchmark.
- A ticker lacking enough history is returned as `SEM_LEITURA`.
- The indicator has three labels only: `OBSERVAR`, `NEUTRO`, and `FRACO`.
- Historical tests include 14 bps round-trip cost/slippage in the broader
  walk-forward strategy validation. The 13-month sample produced +23.84%
  total return but a -24.45% maximum drawdown and a monthly t-stat of 0.872.
  It is promising research, not production evidence.
- The standalone setup audit found no simple indicator setup ready for
  automation. In particular, raw breakouts, Bollinger squeezes and short
  breakdown setups remain research-only.

## API

`GET /api/technical/edge?symbols=AAPL,MSFT,NVDA,AMD&period=2y`

The endpoint returns each raw feature, signed percentile contribution, rank,
label, and the universe size. It requires login like the other technical API
routes.
