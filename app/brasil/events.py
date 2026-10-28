"""Eventos que mexem com a bolsa brasileira: agenda e impacto MEDIDO no Ibovespa.

Agenda:
- Copom: calendário oficial do BCB de 2026 (bcb.gov.br/publicacoes/calendarioreunioescopom),
  conferido em 28/10/2026 contra as decisões já publicadas (mar, abr, jun, ago, set batem).
  A próxima data também é confirmada pela série 432 do SGS, que já traz a vigência nova.
- FOMC: reaproveita app/market_data/fomc_schedule.py.
- Eleições: TSE. 2026: 1º turno em 04/10 e 2º turno em 25/10. Posse presidencial em
  05/01/2027 (EC 111/2021 mudou a data, antes era 1º de janeiro).
- IPCA: o IBGE divulga por volta do dia 10; a data exata fica no calendário do IBGE.
- Vencimento do Ibovespa futuro: quarta-feira mais próxima do dia 15 dos meses pares (B3).

Impacto (descritivo, não é estudo pré-registrado e NÃO prevê direção):
movimento absoluto do Ibovespa no pregão que reage ao evento, comparado com a média
de todos os pregões dos últimos 10 anos. Copom decide depois do fechamento (≈18h30),
então o pregão que reage é o seguinte. Eleição acontece no domingo: reage na segunda.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import httpx
import pandas as pd

from app import response_cache
from app.market_data import service as market_data
from app.market_data.fomc_schedule import FOMC_DECISION_DATES

logger = logging.getLogger(__name__)

COPOM_2026 = (
    date(2026, 1, 28), date(2026, 3, 18), date(2026, 4, 29), date(2026, 6, 17),
    date(2026, 8, 5), date(2026, 9, 16), date(2026, 11, 4), date(2026, 12, 9),
)

# (data, rótulo). Domingos de votação; a reação aparece no pregão seguinte.
ELECTIONS = (
    (date(2018, 10, 7), "Eleição 2018 · 1º turno"),
    (date(2018, 10, 28), "Eleição 2018 · 2º turno"),
    (date(2022, 10, 2), "Eleição 2022 · 1º turno"),
    (date(2022, 10, 30), "Eleição 2022 · 2º turno"),
    (date(2026, 10, 4), "Eleição 2026 · 1º turno"),
    (date(2026, 10, 25), "Eleição 2026 · 2º turno"),
)

POSSE_2027 = date(2027, 1, 5)

COPOM_HISTORY_URL = "https://www.bcb.gov.br/api/servico/sitebcb/copom/comunicados"


def _ibov_futures_expiry(year: int, month: int) -> date:
    """Quarta-feira mais próxima do dia 15."""
    d15 = date(year, month, 15)
    offset = (2 - d15.weekday()) % 7  # 2 = quarta
    after = d15 + timedelta(days=offset)
    before = after - timedelta(days=7)
    return before if (d15 - before) < (after - d15) else after


def upcoming(today: date | None = None, days: int = 120) -> list[dict]:
    today = today or date.today()
    end = today + timedelta(days=days)
    out: list[dict] = []

    def add(d: date, kind: str, title: str, why: str, impact: str, approx: bool = False):
        if today <= d <= end:
            out.append({"date": d.isoformat(), "kind": kind, "title": title, "why": why, "impact": impact, "approximate": approx})

    for d in COPOM_2026:
        add(d, "copom", "Copom decide a Selic", "A Selic mexe no rendimento da renda fixa, no preço dos títulos prefixados e IPCA+ e no valor das empresas.", "alto")
    for d in FOMC_DECISION_DATES:
        add(d, "fomc", "Fed decide os juros dos EUA", "Juros americanos mexem no dólar e no fluxo de dinheiro estrangeiro para a B3.", "médio")
    for d, label in ELECTIONS:
        add(d, "eleicao", label, "Eleição muda a expectativa sobre gasto público, juros e estatais. Costuma gerar os maiores movimentos do ano.", "muito alto")
    add(POSSE_2027, "eleicao", "Posse presidencial", "Primeiros anúncios de equipe econômica e metas fiscais.", "médio")
    month = date(today.year, today.month, 1)
    while month <= end:
        add(month.replace(day=10), "ipca", f"IPCA de {_month_name(month - timedelta(days=1))}", "A inflação muda a expectativa para a Selic e corrige o Tesouro IPCA+.", "médio", approx=True)
        if month.month % 2 == 0:
            add(_ibov_futures_expiry(month.year, month.month), "vencimento", "Vencimento do Ibovespa futuro", "Dia de ajuste de posições grandes; o índice pode oscilar mais no fim do pregão.", "baixo")
        month = (month + timedelta(days=32)).replace(day=1)
    out.sort(key=lambda e: e["date"])
    return out


_MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def _month_name(d: date) -> str:
    return _MONTHS[d.month - 1]


def _copom_history() -> list[tuple[date, str]]:
    res = httpx.get(COPOM_HISTORY_URL, params={"quantidade": 90}, timeout=15.0, headers={"User-Agent": "OneB/1.0"})
    res.raise_for_status()
    return [(date.fromisoformat(r["dataReferencia"]), r["titulo"]) for r in res.json()["conteudo"]]


def _reaction_session(index: pd.DatetimeIndex, event_day: date, same_day: bool) -> pd.Timestamp | None:
    """Primeiro pregão em que o evento já é conhecido."""
    days = pd.Index([ts.date() for ts in index])
    after = [i for i, d in enumerate(days) if (d >= event_day if same_day else d > event_day)]
    return index[after[0]] if after else None


def measure_impact(bars: pd.DataFrame, copom: list[tuple[date, str]]) -> dict:
    close = bars["close"].dropna()
    ret = close.pct_change().dropna() * 100
    base = float(ret.abs().mean())

    def group(events: list[tuple[date, str]], same_day: bool) -> dict:
        rows = []
        for d, label in events:
            ts = _reaction_session(ret.index, d, same_day)
            if ts is None or (ts.date() - d).days > 5:
                continue
            rows.append({"event_date": d.isoformat(), "session": ts.date().isoformat(), "label": label, "return_pct": round(float(ret.loc[ts]), 2)})
        if not rows:
            return {"n": 0, "rows": []}
        mean_abs = sum(abs(r["return_pct"]) for r in rows) / len(rows)
        return {"n": len(rows), "mean_abs_pct": round(mean_abs, 2), "ratio": round(mean_abs / base, 2) if base else None, "rows": rows}

    first = ret.index[0].date()
    return {
        "since": first.isoformat(),
        "normal_abs_pct": round(base, 2),
        "copom": group([e for e in copom if e[0] >= first], same_day=False),
        "fomc": group([(d, "FOMC") for d in FOMC_DECISION_DATES if d >= first and d <= ret.index[-1].date()], same_day=True),
        "eleicao": group([e for e in ELECTIONS if e[0] >= first], same_day=False),
        "note": "Descritivo: mostra o tamanho do movimento, não a direção. Poucas eleições na amostra; cada uma tem seu contexto.",
    }


def _load_impact() -> dict:
    bars = market_data.get_bars("^BVSP", period="10y", interval="1d")
    if bars.empty:
        return {"available": False}
    try:
        copom = _copom_history()
    except Exception:
        logger.warning("Histórico do Copom indisponível.", exc_info=True)
        copom = [(d, "Copom") for d in COPOM_2026]
    return {"available": True, **measure_impact(bars, copom)}


def impact() -> dict:
    return response_cache.cached("brasil:events-impact", 6 * 3600, _load_impact)
