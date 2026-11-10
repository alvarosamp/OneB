"""Unified macro-instrument registry for the regime engine.

Routes each tracked instrument to whichever source is actually the primary
publisher of that data: Treasury yields and the dollar index come from
FRED (official, St. Louis Fed); index/commodity/FX futures stay on
yfinance, which has no better free alternative for those. See the
architecture notes in app/regime_engine.py for why this distinction
matters (Tier S vs Tier B data sources).

app.regime_engine and app.routers.regime should import MACRO_INSTRUMENTS,
get_macro_quote and get_macro_history from here, not from yfinance_client.
"""
from __future__ import annotations

from datetime import timezone

import pandas as pd

from app.market_data import fred_client, yfinance_client
from app.market_data import service as market_data_service

# key -> (source, symbol_or_series_id, display_name)
MACRO_INSTRUMENTS: dict[str, tuple[str, str, str]] = {
    "NASDAQ": ("yfinance", yfinance_client.NASDAQ_FUTURES_SYMBOL, "Nasdaq-100 (futuro)"),
    "SP500": ("yfinance", yfinance_client.SP500_FUTURES_SYMBOL, "S&P500 (futuro)"),
    "GOLD": ("yfinance", "GC=F", "Ouro"),
    # Trade-weighted dollar index (broad, goods & services) — FRED's official
    # replacement for the Yahoo DX-Y.NYB proxy.
    "DXY": ("fred", "DTWEXBGS", "Dollar Index (trade-weighted, Fed)"),
    "US2Y": ("fred", "DGS2", "Treasury 2 anos (yield)"),
    "US5Y": ("fred", "DGS5", "Treasury 5 anos (yield)"),
    "US10Y": ("fred", "DGS10", "Treasury 10 anos (yield)"),
    "US30Y": ("fred", "DGS30", "Treasury 30 anos (yield)"),
    "VIX": ("fred", "VIXCLS", "VIX (CBOE, via FRED)"),
    "BRENT": ("yfinance", "BZ=F", "Petroleo Brent"),
    "WTI": ("yfinance", "CL=F", "Petroleo WTI"),
    "EURUSD": ("yfinance", "EURUSD=X", "EUR/USD"),
    "EURBRL": ("yfinance", "EURBRL=X", "EUR/BRL"),
}

# The macro portfolio the user follows day to day.  VIX remains in the wider
# registry as a risk input, but this ordered list mirrors the instruments that
# deserve a dedicated trend board in the UI.
TREND_WATCHLIST = (
    "US2Y",
    "US5Y",
    "US10Y",
    "US30Y",
    "GOLD",
    "BRENT",
    "WTI",
    "NASDAQ",
    "SP500",
    "DXY",
    "EURUSD",
    "EURBRL",
)

TREND_CONTEXT: dict[str, str] = {
    "US2Y": "Juro curto: reage principalmente à trajetória esperada da política monetária dos EUA.",
    "US5Y": "Trecho intermediário da curva: combina expectativa de Fed, inflação e crescimento.",
    "US10Y": "Referência global de desconto: alta do yield tende a apertar as condições financeiras.",
    "US30Y": "Juro longo: sensível a inflação estrutural, prêmio de prazo e risco fiscal.",
    "GOLD": "Ouro em dólar: observe junto de juros reais, dólar e demanda por proteção.",
    "BRENT": "Petróleo global: tendência reflete oferta, geopolítica e demanda internacional.",
    "WTI": "Petróleo dos EUA: complemente a leitura com estoques, oferta e atividade americana.",
    "NASDAQ": "Tecnologia dos EUA: costuma ser sensível a juros longos, liquidez e crescimento.",
    "SP500": "Ações amplas dos EUA: referência para apetite a risco e breadth do mercado.",
    "DXY": "Força ampla do dólar: alta pode apertar liquidez global e pressionar ativos em dólar.",
    "EURUSD": "Força relativa euro/dólar: alta indica euro mais forte frente ao dólar.",
    "EURBRL": "Câmbio euro/real: alta indica euro mais forte e real mais fraco.",
}

FRED_FALLBACKS: dict[str, tuple[str, str]] = {
    # Lower-tier continuity proxies used only when FRED is unavailable.
    "DXY": ("DX-Y.NYB", "Yahoo proxy for ICE U.S. Dollar Index"),
    # Yahoo's ^TNX is quoted as 10x the 10-year yield: 45.0 means 4.50%.
    "US10Y": ("^TNX", "Yahoo CBOE 10Y yield proxy"),
    "VIX": ("^VIX", "Yahoo CBOE VIX proxy"),
}


def _yfinance_yield_proxy(symbol: str, period: str, interval: str, *, refresh: bool = False) -> pd.DataFrame:
    history = market_data_service.get_bars(symbol, period=period, interval=interval, refresh=refresh)
    if history.empty:
        return history
    out = history.copy()
    for column in ["open", "high", "low", "close"]:
        out[column] = out[column] / 10.0
    return out


def _fallback_history(key: str, period: str, interval: str, *, refresh: bool = False) -> pd.DataFrame:
    fallback = FRED_FALLBACKS.get(key.upper())
    if fallback is None:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    symbol, _reason = fallback
    if key.upper() == "US10Y":
        return _yfinance_yield_proxy(symbol, period, interval, refresh=refresh)
    return market_data_service.get_bars(symbol, period=period, interval=interval, refresh=refresh)


def get_macro_quote(key: str, *, refresh: bool = False):
    """Latest quote for one MACRO_INSTRUMENTS entry. Returns an object with
    .symbol/.name/.price/.change_pct/.updated_at regardless of source
    (yfinance_client.IndexQuote or fred_client.FredQuote) — callers
    (regime_engine.store_macro_snapshots) only read those common fields.
    """
    entry = MACRO_INSTRUMENTS.get(key.upper())
    if entry is None:
        return None
    source, symbol, name = entry
    if source == "fred":
        quote = fred_client.get_quote(symbol, name, refresh=refresh)
        if quote is None:
            fallback = FRED_FALLBACKS.get(key.upper())
            if fallback is None:
                return None
            history = _fallback_history(key, period="5d", interval="1d", refresh=refresh)
            if history.empty:
                return None
            close = history["close"].dropna()
            if close.empty:
                return None
            latest = float(close.iloc[-1])
            previous = float(close.iloc[-2]) if len(close) >= 2 else latest
            change_pct = ((latest - previous) / previous * 100) if previous else 0.0
            ts = close.index[-1]
            updated_at = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else pd.Timestamp.utcnow().to_pydatetime()
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            return yfinance_client.IndexQuote(
                symbol=fallback[0],
                name=f"{name} ({fallback[1]})",
                price=latest,
                change_pct=change_pct,
                day_high=latest,
                day_low=latest,
                prev_close=previous,
                updated_at=updated_at,
            )
        return yfinance_client.IndexQuote(
            symbol=symbol,
            name=name,
            price=quote.value,
            change_pct=quote.change_pct,
            day_high=quote.value,
            day_low=quote.value,
            prev_close=quote.value,
            updated_at=quote.updated_at,
        )
    return yfinance_client.get_index_quote(symbol, name)


def get_macro_history(key: str, period: str = "6mo", interval: str = "1d", *, refresh: bool = False) -> pd.DataFrame:
    """Daily history for a MACRO_INSTRUMENTS entry — used for rolling
    correlation/regime calculations, which need a return series rather than
    just the latest quote.
    """
    entry = MACRO_INSTRUMENTS.get(key.upper())
    if entry is None:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    source, symbol, _name = entry
    if source == "fred":
        history = fred_client.get_series(symbol, refresh=refresh)
        if not history.empty:
            return history
        return _fallback_history(key, period, interval, refresh=refresh)
    return market_data_service.get_bars(symbol, period=period, interval=interval, refresh=refresh)
