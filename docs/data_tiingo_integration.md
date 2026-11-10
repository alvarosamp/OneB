# Tiingo integration

Updated: 2026-08-13

## Role in OneB Market

Tiingo is the preferred provider for daily EOD OHLCV used by:

- technical indicators;
- backtests;
- strategy research;
- Mesa Tecnica;
- model and signal validation that depends on adjusted daily candles.

The project still keeps yfinance as a fallback, especially for intraday intervals such as `15m`, because Tiingo EOD only covers daily candles through `/tiingo/daily/<ticker>/prices`.

## Configuration

Set this in `.env`:

```env
MARKET_DATA_PROVIDER=tiingo
TIINGO_API_KEY=your_token_here
```

Never commit a real token. Keep it in `.env` or in the hosting provider's secret manager.

## Authentication

The client uses the documented header form:

```text
Authorization: Token <api-token>
```

This avoids putting the token in URLs, logs, browser history or proxy traces.

## Provider behavior

Data flow:

```text
MarketDataService
  -> Tiingo provider for daily EOD candles
  -> yfinance fallback when Tiingo returns no bars or interval is not daily
  -> normalized OHLCV
  -> provider-specific cache
```

Cache location examples:

```text
data/raw/prices/tiingo/1d/1y/AAPL.csv
data/raw/prices/yfinance/15m/5d/AAPL.csv
```

Metadata is saved next to the CSV with provider, period, interval, row count, time range and quality issues.

## Operational health

`GET /api/operations/health` now exposes:

- `market_data_provider`;
- `active_price_provider`;
- `tiingo_configured`;
- `tiingo_role`;
- `market_data_cache_available`;
- `yfinance_role`.

This makes it clear that Tiingo is the primary EOD research provider and yfinance remains a fallback/compatibility source.

## Licensing note

Tiingo documentation says Basic/Power plans are for internal or personal use and should not be redistributed. For a public SaaS or commercial redistribution, check Tiingo licensing before exposing raw data to users.

Practical MVP rule:

- OK: internal research, personal dashboards, derived indicators for your own use.
- Be careful: selling a public app that redistributes Tiingo raw or near-raw data.
- Safer path: require each user to provide their own Tiingo token or obtain the correct commercial/redistribution license.

