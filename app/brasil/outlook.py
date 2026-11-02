"""Para onde os juros e a inflação devem ir, e quanto o Tesouro paga hoje. Fontes gratuitas:

- Focus (Banco Central, API Olinda): mediana das projeções do mercado para a Selic de
  fim de ano e o IPCA de cada ano. Publicado toda segunda-feira.
- Tesouro Direto (Tesouro Transparente, arquivo PrecoTaxaTesouroDireto.csv): taxa de
  compra de cada título. O arquivo tem o histórico inteiro (~15 MB), mas vem do dia mais
  recente para o mais antigo: lemos só as primeiras linhas, em streaming.

Se uma fonte cair, a função devolve None e o simulador volta às premissas constantes,
avisando na resposta.
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime
from urllib.parse import quote

import httpx

from app import response_cache

logger = logging.getLogger(__name__)

FOCUS_URL = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais"
TESOURO_URL = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/"
    "resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv"
)
HEADERS = {"User-Agent": "OneB/1.0 (educacao financeira)"}

# Títulos que o simulador usa. "Com juros semestrais", Educa+ e Renda+ ficam só na tabela.
SIMULATOR_TITLES = {"Tesouro IPCA+": "tesouro_ipca", "Tesouro Prefixado": "tesouro_prefixado", "Tesouro Selic": "tesouro_selic"}


def _focus_indicator(name: str) -> tuple[str, dict[int, float]]:
    params = {
        "$filter": f"Indicador eq '{name}' and baseCalculo eq 0",
        "$orderby": "Data desc",
        "$top": "10",
        "$format": "json",
        "$select": "Data,DataReferencia,Mediana",
    }
    # O OData do BCB recusa espaço codificado como "+" (padrão do httpx): exige %20.
    query = "&".join(f"{k}={quote(v, safe=',')}" for k, v in params.items())
    res = httpx.get(f"{FOCUS_URL}?{query}", timeout=20.0, headers=HEADERS)
    res.raise_for_status()
    rows = res.json()["value"]
    if not rows:
        raise ValueError(f"Focus sem dados para {name}")
    latest = rows[0]["Data"]
    return latest, {int(r["DataReferencia"]): float(r["Mediana"]) for r in rows if r["Data"] == latest}


def _load_focus() -> dict | None:
    try:
        as_of, selic = _focus_indicator("Selic")
        _, ipca = _focus_indicator("IPCA")
    except Exception:
        logger.warning("Focus (BCB) indisponível.", exc_info=True)
        return None
    years = sorted(set(selic) & set(ipca))
    return {"as_of": as_of, "source": "Boletim Focus (Banco Central), mediana do mercado",
            "years": [{"year": y, "selic": selic[y], "ipca": ipca[y]} for y in years]}


def focus() -> dict | None:
    return response_cache.cached("brasil:focus", 12 * 3600, _load_focus, degraded=lambda d: d is None)


def parse_tesouro_lines(lines) -> dict:
    """Lê as linhas do CSV (cabeçalho + dados) e fica só com o dia mais recente (o primeiro)."""
    reader = csv.reader(lines, delimiter=";")
    header = next(reader)
    idx = {name: i for i, name in enumerate(header)}
    titles, base = [], None
    for row in reader:
        if len(row) < len(header):
            continue
        day = row[idx["Data Base"]]
        if base is None:
            base = day
        elif day != base:
            break  # passou para o dia anterior
        num = lambda col: float(row[idx[col]].replace(".", "").replace(",", "."))  # noqa: E731
        maturity = datetime.strptime(row[idx["Data Vencimento"]], "%d/%m/%Y").date()
        price = num("PU Compra Manha")
        titles.append({
            "name": row[idx["Tipo Titulo"]],
            "maturity": maturity.isoformat(),
            "buy_rate": num("Taxa Compra Manha"),
            "unit_price": price,
            # Compra mínima: 1% do título, respeitando o piso de R$ 30.
            "min_investment": round(max(price * 0.01, 30.0), 2),
        })
    if base is None:
        raise ValueError("arquivo do Tesouro vazio")
    titles.sort(key=lambda t: (t["name"], t["maturity"]))
    return {"as_of": datetime.strptime(base, "%d/%m/%Y").date().isoformat(), "titles": titles,
            "source": "Tesouro Transparente (taxas de compra do Tesouro Direto, manhã)"}


def _load_tesouro() -> dict | None:
    try:
        with httpx.stream("GET", TESOURO_URL, timeout=60.0, headers=HEADERS, follow_redirects=True) as res:
            res.raise_for_status()
            buf: list[str] = []
            for chunk in res.iter_text():
                buf.append(chunk)
                # ~70 títulos por dia; 40 KB cobrem com folga o dia mais recente e o começo do anterior.
                if sum(len(c) for c in buf) > 40_000:
                    break
        text = "".join(buf)
        lines = text.splitlines()[:-1]  # a última linha pode ter vindo cortada
        return parse_tesouro_lines(io.StringIO("\n".join(lines)))
    except Exception:
        logger.warning("Tesouro Direto indisponível.", exc_info=True)
        return None


def tesouro() -> dict | None:
    return response_cache.cached("brasil:tesouro", 6 * 3600, _load_tesouro, degraded=lambda d: d is None)


def pick_title(data: dict | None, name: str, target: date) -> dict | None:
    """Título para levar até o vencimento, perto da data do objetivo.

    1. O que vence até 12 meses ANTES do objetivo (o mais tardio): leva até o fim sem
       vender no meio, e o pouco que sobra fica no Tesouro Selic.
    2. Senão, o primeiro que vence depois (vender antes expõe à oscilação de preço).
    3. Senão (prazo além de todos), o mais longo.
    """
    if not data:
        return None
    options = [t for t in data["titles"] if t["name"] == name]
    if not options:
        return None
    due = lambda t: date.fromisoformat(t["maturity"])  # noqa: E731
    before = [t for t in options if 0 <= (target - due(t)).days <= 366]
    if before:
        return max(before, key=due)
    after = [t for t in options if due(t) >= target]
    if after:
        return min(after, key=due)
    return max(options, key=due)
