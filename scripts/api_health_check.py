"""Calls every data-provider function this app actually uses against the
real API and reports pass/fail — not a config check ("is the key set"), a
behavior check ("does the call return usable data right now").

Motivation: app.market_data.fmp_client.get_economic_calendar looked
correctly configured (key present, code ran, exceptions caught) for
almost a year while silently returning [] on every call, because FMP
retired the endpoint underneath it and the fail-open exception handler
swallowed the 403 without anyone noticing. A key being present proves
nothing about the endpoint still existing. This script exists so that
class of failure gets caught by running it, not by a user noticing a
feature has been empty for months.

Run: python -m scripts.api_health_check
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from app.config import settings
from app.market_data import finnhub_client, fmp_client, fred_client, tiingo_client, yfinance_client
from app.market_data import service as market_data_service

CHECK_SYMBOL = "AAPL"

results: list[dict] = []


def check(provider: str, call: str, fn, *, ok_fn=None) -> None:
    """Runs `fn()`, records pass/fail. `ok_fn(result) -> bool` decides
    success when the default "truthy and non-empty" check isn't right
    (e.g. a Quote object where `bool()` isn't meaningful).
    """
    try:
        result = fn()
    except Exception as exc:
        results.append({"provider": provider, "call": call, "status": "ERRO", "detalhe": f"{type(exc).__name__}: {exc}"})
        return

    if ok_fn is not None:
        passed = ok_fn(result)
    elif isinstance(result, pd.DataFrame):
        passed = not result.empty
    elif result is None:
        passed = False
    elif isinstance(result, (list, dict)):
        passed = len(result) > 0
    else:
        passed = True

    detail = ""
    if isinstance(result, pd.DataFrame):
        detail = f"{len(result)} linhas"
    elif isinstance(result, list):
        detail = f"{len(result)} itens"
    elif result is not None:
        detail = str(result)[:120]

    results.append({"provider": provider, "call": call, "status": "OK" if passed else "VAZIO/FALHOU", "detalhe": detail})


def main() -> None:
    today = date.today()

    print("Configuracao de keys:")
    print(f"  FINNHUB_API_KEY: {'set' if settings.finnhub_api_key else 'AUSENTE'}")
    print(f"  FMP_API_KEY:     {'set' if settings.fmp_api_key else 'AUSENTE'}")
    print(f"  FRED_API_KEY:    {'set' if settings.fred_api_key else 'AUSENTE'}")
    print(f"  TIINGO_API_KEY:  {'set' if settings.tiingo_api_key else 'AUSENTE'}")
    print(f"  MARKET_DATA_PROVIDER: {settings.market_data_provider}")
    print()

    # --- market data service (Tiingo EOD primary + yfinance fallback) ---
    check("market_data", "get_bars(AAPL, 1d)", lambda: market_data_service.get_bars(CHECK_SYMBOL, period="5d", interval="1d", refresh=True))
    check("tiingo", "get_history(AAPL, 1d)", lambda: tiingo_client.get_history(CHECK_SYMBOL, period="5d", interval="1d"))
    check("market_data", "get_bars(AAPL, 15m fallback)", lambda: market_data_service.get_bars(CHECK_SYMBOL, period="5d", interval="15m", refresh=True))

    # --- yfinance direct helpers (sem key) ---
    check("yfinance", "get_usd_brl_quote()", lambda: yfinance_client.get_usd_brl_quote())
    check("yfinance", "get_gold_quote()", lambda: yfinance_client.get_gold_quote())
    check("yfinance", "get_nasdaq_quote()", lambda: yfinance_client.get_nasdaq_quote())
    check("yfinance", "get_sp500_quote()", lambda: yfinance_client.get_sp500_quote())

    # --- Finnhub ---
    check("finnhub", "get_quote(AAPL)", lambda: finnhub_client.get_quote(CHECK_SYMBOL), ok_fn=lambda r: r is not None and r.price > 0)
    check(
        "finnhub",
        "get_company_news(AAPL)",
        lambda: finnhub_client.get_company_news(CHECK_SYMBOL, today - timedelta(days=7), today),
    )
    check("finnhub", "get_market_news()", lambda: finnhub_client.get_market_news("general"))
    check(
        "finnhub",
        "get_earnings_calendar()",
        lambda: finnhub_client.get_earnings_calendar(today, today + timedelta(days=30)),
    )

    # --- FMP ---
    check("fmp", "get_key_metrics(AAPL)", lambda: fmp_client.get_key_metrics(CHECK_SYMBOL))
    check("fmp", "get_income_statement(AAPL)", lambda: fmp_client.get_income_statement(CHECK_SYMBOL))

    # --- FRED ---
    check("fred", "get_series(DGS10)", lambda: fred_client.get_series("DGS10"))
    check("fred", "get_quote(DGS10)", lambda: fred_client.get_quote("DGS10", "Treasury 10Y"), ok_fn=lambda r: r is not None)
    check(
        "fred",
        "get_economic_calendar()",
        lambda: fred_client.get_economic_calendar(today, today + timedelta(days=30)),
    )

    df = pd.DataFrame(results)
    pd.set_option("display.width", 140)
    pd.set_option("display.max_colwidth", 80)
    print(df.to_string(index=False))

    failures = df[df["status"] != "OK"]
    print(f"\n{len(df) - len(failures)}/{len(df)} chamadas OK.")
    if not failures.empty:
        print("\nFALHAS — investigar antes de confiar nesses provedores em produção:")
        print(failures.to_string(index=False))


if __name__ == "__main__":
    main()
