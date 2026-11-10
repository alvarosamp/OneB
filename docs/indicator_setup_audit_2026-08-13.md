# Indicator and setup audit - Tiingo EOD

Date: 2026-08-13

## Summary

The project moved from "data is now reliable" to "which technical evidence is worth building into product workflows".

Status: promising for research, not ready for automated execution.

## Data base

- Provider: Tiingo EOD.
- Universe: 24 Nasdaq/US large-cap symbols.
- Period: 2 years.
- Interval: 1d.
- Data reliability gate: PASS.
- Equity failures: 0.
- Macro failures: 0.

## Audits run

### Explicit setup audit

Command:

```bash
python -m scripts.audit_indicator_setups
```

Output:

```text
data/indicator_setup_audit.json
```

Tested setups:

- `trend_pullback_long`
- `volume_breakout_long`
- `macd_momentum_long`
- `bollinger_squeeze_breakout_long`
- `rsi_reversal_long`
- `adx_trend_continuation_long`
- `breakdown_short`
- `pullback_fail_short`

Result:

No single simple setup passed the bar for production playbook automation.

Best isolated setup:

| Setup | Signals | Avg 5d net return | Win rate | Profit factor | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| `rsi_reversal_long` | 38 | 0.5923% | 50.00% | 1.5171 | RESEARCH |

Useful nuance:

- `rsi_reversal_long` worked better in trend regime than high-volatility regime.
- `macd_momentum_long` and `volume_breakout_long` looked weak overall, but improved in trend regime.
- Short setups were not reliable in this universe/window.
- Bollinger squeeze breakout was weak and should not be prioritized for MVP automation.

### Statistical edge audit

Command:

```bash
python -m scripts.statistical_edge_audit
```

Output:

```text
data/statistical_edge_audit.json
```

Result:

- Rows: 10,368.
- Usable features: 40.
- Primary horizon: 5 days.

Top 5-day cross-sectional features:

| Feature | Mean IC | t-stat | Positive day rate |
| --- | ---: | ---: | ---: |
| `mom_accel_5v20` | -0.04292 | -3.416 | 45.37% |
| `adx14` | 0.04192 | 3.454 | 59.26% |
| `ret_5d` | -0.03784 | -2.763 | 46.06% |
| `rel_ret_5d_vs_qqq` | -0.03784 | -2.763 | 46.06% |
| `annualized_volatility` | 0.03717 | 2.588 | 55.79% |

Interpretation:

- ADX and volatility showed positive cross-sectional information.
- Recent 5d momentum and momentum acceleration were mean-reverting in this sample.
- The best signal is not "buy every breakout"; it is a ranked, multi-feature selection problem.

### Consensus feature validation

Consensus features:

- `mom_accel_5v20`
- `adx14`
- `ret_5d`
- `rel_ret_5d_vs_qqq`
- `annualized_volatility`
- `macd_hist_slope_3d`
- `high20_breakout_pct`
- `ema20_50_gap_pct`

Consensus result:

| Metric | Value |
| --- | ---: |
| Days | 432 |
| Mean spread | 0.78498% |
| Median spread | 0.80038% |
| t-stat | 3.742 |
| Hit rate | 57.64% |

This is the strongest research result in this audit.

### Cross-sectional strategy validation

Command:

```bash
python -m scripts.cross_sectional_strategy_validation
```

Output:

```text
data/cross_sectional_strategy_validation.json
```

Result:

| Metric | Value |
| --- | ---: |
| Months | 13 |
| Rebalance periods | 58 |
| Total return | 23.836% |
| Annualized approx return | 21.8161% |
| Max drawdown | -24.4469% |
| Monthly hit rate | 61.54% |
| Mean monthly return | 1.9601% |
| Monthly t-stat | 0.872 |

Interpretation:

The strategy is promising, but not production-ready. The return is interesting, but the drawdown and low monthly t-stat mean it needs stricter risk filters, lower turnover and more validation windows.

## Product decisions

### Implement first

1. Multi-feature ranking card in Mesa Tecnica:
   - ADX trend strength.
   - Annualized volatility / ATR.
   - 5d momentum acceleration.
   - Relative 5d return vs QQQ.
   - EMA20/EMA50 gap.

2. Regime-aware setup labels:
   - trend continuation only when ADX/trend regime agrees;
   - RSI reversal only when high-volatility regime is not active;
   - breakout with volume should stay "watch", not "buy".

3. Education content:
   - "Por que indicador isolado falha"
   - "Como combinar ADX, volatilidade e momentum"
   - "Quando RSI reversao e pesquisa, nao sinal"

### Do not automate yet

- `breakdown_short`
- `bollinger_squeeze_breakout_long`
- raw `volume_breakout_long`
- raw `trend_pullback_long`

These should remain as study/playbook examples until filters improve.

## Next engineering tasks

1. Add a `TechnicalEdgeScore` API response for each symbol:
   - feature ranks;
   - consensus score;
   - regime;
   - reason;
   - source provider.

2. Add a Mesa Tecnica panel:
   - rank watchlist by consensus edge;
   - show top 3 positive and bottom 3 avoid/weak;
   - show feature contribution.

3. Add guardrails:
   - no trade in high-vol regime unless setup explicitly supports it;
   - downgrade breakout to WATCH when volume or ADX disagrees;
   - cap risk when monthly drawdown proxy is bad.

4. Re-run validation with:
   - 5-year history if Tiingo plan/data availability allows;
   - transaction costs sensitivity: 10, 20, 40 bps;
   - hold periods: 3, 5, 10, 20 days;
   - separate bull/bear/risk-off regimes.

