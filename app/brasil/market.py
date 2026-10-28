"""Retrato da bolsa brasileira e comparativo histórico, só com dados (sem 'compre').

- snapshot(): índices, ETFs, ações e FIIs muito negociados com preço, variação no dia,
  retorno em 12 meses, volatilidade, maior queda e dividendos em 12 meses (Yahoo, ~15 min
  de atraso). A lista mostra os mais negociados, NÃO é seleção de investimento.
- history(): quanto R$ 1.000 viraram em 1, 5 e 10 anos no CDI, IPCA, Ibovespa e dólar.
  O Ibovespa é índice de retorno total (reinveste dividendos), por isso a comparação é justa.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import numpy as np
import pandas as pd

from app import response_cache
from app.brasil import rates
from app.market_data import service as market_data

logger = logging.getLogger(__name__)

UNIVERSE = [
    # (símbolo, rótulo, grupo, descrição)
    ("^BVSP", "Ibovespa", "indice", "As ~85 ações mais negociadas da B3"),
    ("USDBRL=X", "Dólar", "indice", "Reais por 1 dólar"),
    ("BOVA11.SA", "BOVA11", "etf", "ETF do Ibovespa"),
    ("SMAL11.SA", "SMAL11", "etf", "ETF de empresas menores (small caps)"),
    ("DIVO11.SA", "DIVO11", "etf", "ETF de empresas boas pagadoras de dividendos"),
    ("IVVB11.SA", "IVVB11", "etf", "ETF do S&P 500 (EUA) em reais"),
    ("XFIX11.SA", "XFIX11", "etf", "ETF de fundos imobiliários (IFIX)"),
    ("PETR4.SA", "PETR4", "acao", "Petrobras · petróleo"),
    ("VALE3.SA", "VALE3", "acao", "Vale · mineração"),
    ("ITUB4.SA", "ITUB4", "acao", "Itaú · banco"),
    ("BBDC4.SA", "BBDC4", "acao", "Bradesco · banco"),
    ("BBAS3.SA", "BBAS3", "acao", "Banco do Brasil · banco"),
    ("B3SA3.SA", "B3SA3", "acao", "B3 · bolsa"),
    ("WEGE3.SA", "WEGE3", "acao", "WEG · indústria"),
    ("ABEV3.SA", "ABEV3", "acao", "Ambev · bebidas"),
    ("SUZB3.SA", "SUZB3", "acao", "Suzano · papel e celulose"),
    ("RENT3.SA", "RENT3", "acao", "Localiza · aluguel de carros"),
    ("EQTL3.SA", "EQTL3", "acao", "Equatorial · energia"),
    ("RADL3.SA", "RADL3", "acao", "Raia Drogasil · farmácias"),
    ("HGLG11.SA", "HGLG11", "fii", "FII de galpões logísticos"),
    ("KNRI11.SA", "KNRI11", "fii", "FII de escritórios e galpões"),
    ("XPML11.SA", "XPML11", "fii", "FII de shoppings"),
    ("MXRF11.SA", "MXRF11", "fii", "FII de títulos imobiliários (papel)"),
]


def _dividends_12m(symbol: str) -> float | None:
    try:
        import yfinance as yf

        div = yf.Ticker(symbol).dividends
        if div is None or div.empty:
            return 0.0
        cutoff = pd.Timestamp.now(tz=div.index.tz) - pd.Timedelta(days=365)
        return float(div[div.index >= cutoff].sum())
    except Exception:
        logger.warning("Dividendos de %s indisponíveis.", symbol, exc_info=True)
        return None


def metrics(close: pd.Series) -> dict:
    close = close.dropna()
    # Desdobramento/agrupamento sem ajuste no Yahoo aparece como salto > 50% em um dia
    # (ex.: XPML11 em 01/2026). Medimos só depois da última quebra e avisamos.
    jumps = close.pct_change().abs() > 0.5
    break_at = None
    if jumps.any():
        break_at = close.index[jumps.to_numpy().nonzero()[0][-1]]
        close = close[close.index >= break_at]
    if len(close) < 2:
        return {}
    last = float(close.iloc[-1])
    ret = close.pct_change().dropna()
    year = close[close.index >= close.index[-1] - pd.Timedelta(days=365)]
    peak = year.cummax()
    return {
        "price": round(last, 4 if last < 10 else 2),
        "change_pct": round(float(ret.iloc[-1] * 100), 2),
        "return_12m_pct": round(float((last / year.iloc[0] - 1) * 100), 2) if len(year) > 1 else None,
        "volatility_pct": round(float(ret.tail(252).std() * np.sqrt(252) * 100), 1),
        "max_drawdown_pct": round(float(((year / peak) - 1).min() * 100), 1),
        "as_of": close.index[-1].date().isoformat(),
        "data_break": break_at.date().isoformat() if break_at is not None else None,
    }


def _row(item: tuple[str, str, str, str]) -> dict:
    symbol, label, group, desc = item
    out = {"symbol": symbol.replace(".SA", ""), "label": label, "group": group, "description": desc, "available": False}
    try:
        bars = market_data.get_bars(symbol, period="1y", interval="1d")
    except Exception:
        logger.warning("Sem barras de %s.", symbol, exc_info=True)
        return out
    m = metrics(bars["close"]) if not bars.empty else {}
    if not m:
        return out
    out.update(m, available=True, stale=bool(bars.attrs.get("cache_fallback")))
    if group in ("acao", "fii", "etf") and symbol.endswith(".SA"):
        div = _dividends_12m(symbol)
        out["dividends_12m"] = None if div is None else round(div, 2)
        # ETF que reinveste (BOVA11, DIVO11...) aparece com zero: mostramos "—", não 0%.
        out["dividend_yield_pct"] = round(div / m["price"] * 100, 2) if div and m["price"] and not m.get("data_break") else None
    return out


def _load_snapshot() -> dict:
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(_row, UNIVERSE))
    return {
        "rows": rows,
        "source": "Yahoo Finance (cerca de 15 minutos de atraso)",
        "note": "Lista dos ativos mais negociados de cada grupo, para estudo. Não é seleção nem recomendação.",
    }


def snapshot() -> dict:
    return response_cache.cached("brasil:snapshot", 30 * 60, _load_snapshot)


def growth_table(monthly: dict[str, pd.Series], horizons=(12, 60, 120)) -> list[dict]:
    """R$ 1.000 aplicados há N meses em cada série de retorno mensal (%)."""
    out = []
    for months in horizons:
        row = {"months": months}
        for name, series in monthly.items():
            s = series.dropna()
            row[name] = round(1000 * float(np.prod(1 + s.tail(months) / 100)), 0) if len(s) >= months else None
        out.append(row)
    return out


def _price_monthly(symbol: str) -> pd.Series:
    bars = market_data.get_bars(symbol, period="max", interval="1d")
    if bars.empty:
        return pd.Series(dtype=float)
    close = bars["close"].dropna()
    close.index = pd.DatetimeIndex([ts.date() for ts in close.index])
    monthly = close.resample("ME").last()
    ret = monthly.pct_change() * 100
    ret.index = ret.index.strftime("%Y-%m")
    return ret.dropna()


def _poupanca_monthly(start: date, end: date) -> pd.Series | None:
    """Série 195 (diária, rendimento de cada aniversário): fica a do dia 1, mês a mês.

    Consultas longas de série diária falham no SGS (502); buscamos de 3 em 3 anos."""
    rows: list[tuple[str, float]] = []
    year = start.year
    try:
        while year <= end.year:
            chunk_end = min(date(year + 2, 12, 31), end)
            rows += rates.fetch_daily_with_day(195, date(year, 1, 1), chunk_end)
            year += 3
    except Exception:
        logger.warning("Poupança (SGS 195) indisponível.", exc_info=True)
        return None
    return pd.Series({d[:7]: v for d, v in rows if d.endswith("-01")})


def _load_history() -> dict:
    today = date.today()
    start = date(today.year - 11, today.month, 1)
    series: dict[str, pd.Series] = {}
    errors = []
    for name, code in (("cdi", 4391), ("ipca", 433)):
        try:
            rows = rates.fetch_monthly(code, start, today)
            series[name] = pd.Series({k: v for k, v in rows})
        except Exception:
            logger.warning("Série %s do BCB indisponível.", code, exc_info=True)
            errors.append(name)
    for name, symbol in (("ibovespa", "^BVSP"), ("dolar", "USDBRL=X")):
        s = _price_monthly(symbol)
        if s.empty:
            errors.append(name)
        else:
            series[name] = s
    # Alinha no período comum e só com meses fechados (o mês corrente distorce).
    current = today.strftime("%Y-%m")
    common = sorted(set.intersection(*(set(s.index) for s in series.values())) - {current}) if series else []
    aligned = {k: v.reindex(common) for k, v in series.items()}
    poup = _poupanca_monthly(start, today)
    if poup is not None and common:
        aligned["poupanca"] = poup.reindex(common)
    else:
        errors.append("poupanca")
    table = growth_table(aligned) if aligned else []
    return {
        "table": table,
        "last_month": common[-1] if common else None,
        "missing": errors,
        "note": "Ibovespa é índice de retorno total (dividendos reinvestidos). CDI e IPCA do Banco Central. "
        "Antes de imposto e custos. Na última década a bolsa passou longos períodos rendendo menos que o CDI: "
        "por isso renda variável é para prazo longo e só com parte do dinheiro.",
    }


def history() -> dict:
    return response_cache.cached("brasil:history", 6 * 3600, _load_history)
