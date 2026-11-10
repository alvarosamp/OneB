# Evidence report for the BEAR-regime candidate

`scripts.regime_signal_evidence` produces the statistical table for the only
candidate signal that replicated across the project's five- and ten-year
research windows. It does not update an application model or authorize a
trading decision.

## Why this exists

An AUC reported once is not enough for a paper. Equity observations from the
same date are correlated, so treating every symbol-date row as independent
would make confidence intervals too narrow. The report therefore resamples
whole calendar dates and evaluates a held-out, newest BEAR-regime period.

It compares the preregistered two-feature candidate
`annualized_volatility + atr_pct` with its one-feature ablations. The
permutation null shuffles labels only within dates, preserving the daily
cross-sectional label balance.

## Run

```bash
MARKET_HISTORY_PERIOD=10y python -m scripts.regime_signal_evidence
```

The output is `data/research/regime_signal_evidence.json`, accompanied by
`regime_signal_evidence.json.manifest.json`. The manifest records the Git
commit, executable parameters, dependency versions, input/output checksums and
the fresh data-gate verdict. A failing gate blocks the experiment. For a quick
smoke run, use `--bootstrap 200 --permutations 200`; do not use that smaller
run in a manuscript.

## Paper reporting checklist

- State the universe, data provider, history end date, feature definitions and
  BEAR-regime rule before presenting results.
- Report held-out AUC, date-block 95% CI, Brier score, and the within-date
  permutation p-value for the primary two-feature candidate.
- Report the two one-feature ablations even if they weaken the narrative.
- Keep economic claims separate: confirm fees, turnover, drawdown, and an
  external-universe replication before claiming tradability.
- Save the JSON alongside the git commit and register it with
  `scripts.register_experiment`.

## Economic follow-up

Run `python -m scripts.regime_bear_economic_validation` after producing the
statistical report. It applies the candidate only to newest held-out BEAR
dates, rebalances at non-overlapping five-day intervals, charges configurable
turnover costs, and reports drawdown against an equal-weight reference. Its
output remains `RESEARCH_ONLY`: positive paper results are not permission to
promote the signal to a production decision.
