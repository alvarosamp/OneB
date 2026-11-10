# Risk Policy

The risk engine should become portfolio-aware before any live execution path.

It must understand:

- capital and cash
- gross and net exposure
- single-name exposure
- sector exposure
- correlation and beta
- drawdown and daily loss
- volatility and liquidity
- earnings windows
- stale or conflicting data
- broker state

## Kill Switch

No strategy or model can bypass:

```text
MAX_DAILY_LOSS
MAX_DRAWDOWN
MAX_POSITION
MAX_SECTOR
MAX_GROSS_EXPOSURE
MAX_OPEN_ORDERS
MAX_SLIPPAGE
MAX_DATA_AGE
BROKER_DISCONNECTED
DATA_CONFLICT
MODEL_DEGRADED
```

Before broker integration, paper, backtest and live paths should share the same
strategy and risk engine, differing only by execution adapter.

Current implementation:

- `app.risk_engine.evaluate_decision` checks quality gate failures, suggested
  size, single-symbol exposure and stale local data.
- The decision engine downgrades blocked actionable recommendations to
  `NO_TRADE`.
