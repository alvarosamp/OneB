# Data audit - Tiingo EOD integration

Date: 2026-08-13

## Summary

Status: PASS.

The project was re-audited after configuring Tiingo as the primary EOD provider.

## Checks run

### API health

Command:

```bash
python -m scripts.api_health_check
```

Result:

- 16/16 provider calls OK.
- Tiingo direct EOD check OK.
- Market data service daily check OK.
- Market data service intraday fallback OK.
- Finnhub, FMP, FRED and yfinance helper calls OK.

### Tiingo EOD cache refresh

Refreshed 24 core symbols with:

- period: `2y`
- interval: `1d`
- provider: `tiingo`

Result:

- 24/24 symbols loaded from Tiingo.
- 501 candles per symbol.
- No fallback needed for EOD.
- No metadata warnings.

Symbols:

```text
AAPL, MSFT, NVDA, AMD, AMZN, GOOGL, META, TSLA, AVGO, NFLX, COST, ADBE,
CSCO, QCOM, PLTR, SNAP, REGN, VRTX, GILD, AMGN, MDLZ, HON, PYPL, CMCSA
```

### Data reliability gate

Command:

```bash
python -m scripts.data_reliability_gate
```

Result:

- Status: PASS.
- Failure count: 0.
- Equities OK: 24.
- Macro OK: 3.

Macro coverage:

| Series | Rows | Last value |
| --- | ---: | ---: |
| DXY | 5164 | 119.0649 |
| US10Y | 16135 | 4.65 |
| VIX | 9247 | 14.9 |

### Watchlist data-quality comparison

Active DB watchlist during audit:

- AAPL

Initial result:

- Confidence: MEDIUM.
- Divergence: 2.97%.
- Cause: stale local snapshot from 2026-08-08 was compared against fresh Finnhub and Tiingo values.

Fix applied:

- `app.data_quality` now ignores stale providers when computing cross-provider divergence.
- Local snapshots older than 24h are ignored for comparison.
- Tiingo/yfinance EOD providers receive a 3-day tolerance because daily candles are expected to lag live quotes.

Final AAPL result:

- Confidence: HIGH.
- Finnhub: available.
- Tiingo: available.
- Local snapshot: available but ignored as stale.
- Comparable divergence: 0.62%.

## Code changes made during audit

- `scripts/api_health_check.py`
  - Added Tiingo key/provider reporting.
  - Added direct Tiingo EOD check.
  - Renamed candle check from yfinance-only to market data service.
  - Added explicit intraday fallback check.

- `app.data_quality`
  - Added stale-provider filtering.
  - Added `stale_providers_ignored` to the response.
  - Prevented stale local snapshots from lowering confidence when fresh providers agree.

- `app.routers.operations`
  - Kept `yfinance_available` for backwards compatibility.
  - Keeps newer `market_data_cache_available` and Tiingo provider fields.

- `tests/test_api_routes.py`
  - Updated data-quality test timestamp so the test checks provider agreement, not intentional stale data.

## Validation

Targeted tests:

```bash
python -m pytest tests/test_market_data_service.py \
  tests/test_api_routes.py::test_data_quality_compares_multiple_sources \
  tests/test_api_routes.py::test_operations_health_endpoint \
  tests/test_api_routes.py::test_operations_health_marks_yfinance_as_required -q
```

Result:

- 11 passed.

Warnings:

- Pytest cache warning on Windows.
- Starlette/httpx deprecation warning from test client.

Neither warning indicates a data-quality failure.

## Recommendation

The data layer is now strong enough for:

- EOD technical indicators;
- EOD backtests;
- Mesa Tecnica daily analysis;
- model/research experiments that require adjusted candles.

Still avoid treating this as live execution-grade data. Tiingo EOD is not a live broker feed, and Finnhub live quotes can differ from previous daily close during the session.

