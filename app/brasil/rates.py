"""Taxas de referência do Brasil vindas do Banco Central (API SGS, gratuita, sem chave).

Séries:
- 432: meta da Selic (% a.a.)
- 4389: CDI anualizado, base 252 (% a.a.)
- 13522: IPCA acumulado em 12 meses (%)
- 4391: CDI acumulado no mês (% a.m.)  — usado no comparativo histórico
- 433: IPCA do mês (%)                  — idem

Se o BCB não responder, usamos o último valor conhecido (FALLBACK) e marcamos
`stale=True`: a tela avisa que a taxa pode estar desatualizada.
"""
from __future__ import annotations

import logging
from datetime import date, datetime

import httpx

from app import response_cache

logger = logging.getLogger(__name__)

SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
SERIES = {"selic": 432, "cdi": 4389, "ipca_12m": 13522}

# Conferido no BCB em 28/10/2026. Só é usado se a API estiver fora do ar.
FALLBACK = {
    "selic": (13.75, "2026-10-28"),
    "cdi": (13.65, "2026-10-27"),
    "ipca_12m": (4.58, "2026-09-01"),
}

TTL_SECONDS = 6 * 3600


def _parse_date(text: str) -> str:
    return datetime.strptime(text, "%d/%m/%Y").date().isoformat()


def _fetch_last(code: int) -> tuple[float, str]:
    res = httpx.get(f"{SGS_URL.format(code=code)}/ultimos/1", params={"formato": "json"}, timeout=10.0)
    res.raise_for_status()
    row = res.json()[-1]
    return float(row["valor"]), _parse_date(row["data"])


def fetch_daily_with_day(code: int, start: date, end: date) -> list[tuple[str, float]]:
    """Série no intervalo como [(AAAA-MM-DD, valor)]."""
    res = httpx.get(
        SGS_URL.format(code=code),
        params={"formato": "json", "dataInicial": start.strftime("%d/%m/%Y"), "dataFinal": end.strftime("%d/%m/%Y")},
        timeout=40.0,
    )
    res.raise_for_status()
    return [(_parse_date(r["data"]), float(r["valor"])) for r in res.json()]


def fetch_monthly(code: int, start: date, end: date) -> list[tuple[str, float]]:
    """Série mensal (ex.: 4391, 433) como [(AAAA-MM, valor %)]."""
    return [(d[:7], v) for d, v in fetch_daily_with_day(code, start, end)]


def poupanca_annual(selic: float, tr_annual: float = 0.0) -> float:
    """Regra da poupança (Lei 12.703/2012): Selic acima de 8,5% → 0,5% a.m. + TR;
    senão 70% da Selic + TR. TR fica de fora por padrão (perto de zero)."""
    if selic > 8.5:
        base = (1.005 ** 12 - 1) * 100
    else:
        base = selic * 0.7
    return ((1 + base / 100) * (1 + tr_annual / 100) - 1) * 100


def _load(fetch=_fetch_last) -> dict:
    out: dict = {"source": "Banco Central do Brasil (SGS)", "stale": False, "series": {}}
    for name, code in SERIES.items():
        try:
            value, as_of = fetch(code)
        except Exception:  # rede, formato ou API fora do ar
            logger.warning("BCB SGS %s indisponível; usando valor de reserva.", code, exc_info=True)
            value, as_of = FALLBACK[name]
            out["stale"] = True
        # A série 432 já traz a vigência até o próximo Copom (data futura).
        as_of = min(as_of, date.today().isoformat())
        out["series"][name] = {"value": value, "as_of": as_of, "code": code}
    selic = out["series"]["selic"]["value"]
    cdi = out["series"]["cdi"]["value"]
    ipca = out["series"]["ipca_12m"]["value"]
    out.update(
        selic=selic,
        cdi=cdi,
        ipca_12m=ipca,
        poupanca=round(poupanca_annual(selic), 2),
        real_cdi=round(((1 + cdi / 100) / (1 + ipca / 100) - 1) * 100, 2),
    )
    return out


def current() -> dict:
    return response_cache.cached("brasil:rates", TTL_SECONDS, _load)
