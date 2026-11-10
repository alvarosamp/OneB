# Decision Flow

The target decision flow is:

```text
Market Data
  -> Data Quality Gate
  -> Feature / Evidence Builders
  -> Prediction Contract
  -> Risk Engine
  -> Decision Card
  -> Journal / Simulation / Education
```

Only deterministic services should calculate prices, position size, PnL and
risk limits. LLMs explain and summarize; they do not approve risk or execution.

## Decision States

- `STRONG_BUY`
- `BUY`
- `WATCH`
- `NO_TRADE`
- `AVOID`
- `SHORT`
- `STRONG_SHORT`

The current implementation still uses legacy action labels such as
`BUY_CONTROLLED`, `WATCH_BUY`, `SELL_SHORT` and `WATCH_SHORT`. They should be
mapped gradually into the decision states above instead of rewritten all at
once.

## Data Quality Gate

When data quality is below the required threshold, the decision engine must
return `NO_TRADE` with a reason such as `DATA_CONFLICT`, `STALE_DATA` or
`PROVIDER_UNAVAILABLE`.

Current implementation:

- `app.data_quality.quality_gate` classifies the available providers.
- `app.decision_engine` blocks decisions when the gate fails.
- `app.risk_engine` performs the first portfolio/risk checks.
- `app.decision_cards.build_decision_card` packages the result for the UI.
