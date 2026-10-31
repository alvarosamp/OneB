"""Sentimento de manchetes para a pesquisa: relevância por empresa + pontuação por léxico (offline,
determinística) e, quando há chave configurada, por LLM. O LLM só classifica o texto; a decisão
sobre usar ou não o sinal vem do teste estatístico em scripts/research_sentiment.py."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path("data/news/sentiment.csv")

# nomes pelos quais a imprensa cita cada empresa (sem eles, o feed do Yahoo traz muito ruído)
ALIASES: dict[str, list[str]] = {
    "AAPL": ["apple", "iphone", "macbook", "ipad"], "MSFT": ["microsoft", "azure"],
    "NVDA": ["nvidia"], "AMZN": ["amazon", "aws"], "GOOGL": ["google", "alphabet", "youtube", "waymo"],
    "META": ["meta platforms", "facebook", "instagram", "zuckerberg"], "TSLA": ["tesla", "musk"],
    "AVGO": ["broadcom"], "COST": ["costco"], "NFLX": ["netflix"], "AMD": ["advanced micro", "amd"],
    "ADBE": ["adobe"], "CSCO": ["cisco"], "PEP": ["pepsi", "pepsico"], "INTC": ["intel"],
    "QCOM": ["qualcomm"], "TXN": ["texas instruments"], "INTU": ["intuit", "turbotax"],
    "AMGN": ["amgen"], "SBUX": ["starbucks"], "PYPL": ["paypal", "venmo"], "MU": ["micron"],
    "AMAT": ["applied materials"], "BKNG": ["booking holdings", "booking.com"], "GILD": ["gilead"],
    "ISRG": ["intuitive surgical", "da vinci"], "MDLZ": ["mondelez", "oreo"],
    "CMCSA": ["comcast", "nbcuniversal"], "TMUS": ["t-mobile"], "HON": ["honeywell"],
}

POSITIVE = {
    "beat", "beats", "surge", "surges", "soar", "soars", "jump", "jumps", "rally", "rallies", "gain", "gains",
    "record", "upgrade", "upgrades", "upgraded", "outperform", "raises", "raised", "boost", "boosts", "strong",
    "growth", "profit", "profits", "wins", "win", "approval", "approved", "breakthrough", "buy", "bullish",
    "tops", "exceeds", "rebound", "rebounds", "expands", "partnership", "deal", "dividend", "buyback",
}
NEGATIVE = {
    "miss", "misses", "missed", "plunge", "plunges", "tumble", "tumbles", "fall", "falls", "drop", "drops",
    "slump", "slumps", "downgrade", "downgrades", "downgraded", "underperform", "cuts", "cut", "lawsuit",
    "sues", "probe", "investigation", "recall", "warning", "warns", "weak", "loss", "losses", "layoffs",
    "fine", "fined", "ban", "bans", "bearish", "sell", "decline", "declines", "concern", "concerns", "risk",
    "fraud", "delay", "delays", "halt", "halts", "crash", "fears",
}

_WORD = re.compile(r"[a-z][a-z'\-]+")


def is_relevant(symbol: str, headline: str) -> bool:
    """Manchete do ativo só vale se citar a empresa (ou o ticker em maiúsculas)."""
    text = str(headline)
    low = text.lower()
    if any(alias in low for alias in ALIASES.get(symbol, [])):
        return True
    return bool(re.search(rf"\b{re.escape(symbol)}\b", text))


def lexicon_score(headline: str) -> float:
    """(positivas - negativas) / (positivas + negativas), em [-1, 1]; 0 sem nenhuma palavra do léxico."""
    words = _WORD.findall(str(headline).lower())
    pos = sum(w in POSITIVE for w in words)
    neg = sum(w in NEGATIVE for w in words)
    return 0.0 if pos + neg == 0 else (pos - neg) / (pos + neg)


_LLM_SYSTEM = (
    "Você classifica manchetes financeiras pelo efeito provável sobre o preço da ação citada, só pelo "
    "texto da manchete: 1 (positivo), 0 (neutro/irrelevante) ou -1 (negativo). Responda APENAS com um "
    "array JSON de inteiros, um por manchete, na mesma ordem. Não explique."
)


def parse_llm_scores(text: str | None, expected: int) -> list[int] | None:
    if not text:
        return None
    m = re.search(r"\[[^\]]*\]", text, re.S)
    if not m:
        return None
    try:
        values = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if len(values) != expected or not all(isinstance(v, (int, float)) for v in values):
        return None
    return [max(-1, min(1, int(round(v)))) for v in values]


async def llm_scores(pairs: list[tuple[str, str]], batch: int = 25) -> list[int | None]:
    """`pairs` = (symbol, headline). Devolve -1/0/1 por item, ou None onde o LLM falhou."""
    from app import llm_client

    out: list[int | None] = [None] * len(pairs)
    if not llm_client.is_configured():
        return out
    for start in range(0, len(pairs), batch):
        chunk = pairs[start : start + batch]
        prompt = "\n".join(f"{i + 1}. [{sym}] {head}" for i, (sym, head) in enumerate(chunk))
        scores = parse_llm_scores(await llm_client._call(_LLM_SYSTEM, prompt, max_tokens=200), len(chunk))
        if scores is None:
            logger.warning("Resposta do LLM inválida para o lote começando em %d", start)
            continue
        out[start : start + batch] = scores
    return out


def load_cache(path: Path = DEFAULT_PATH) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame(columns=["symbol", "headline", "lexicon", "llm"])


def score_archive(archive: pd.DataFrame, path: Path = DEFAULT_PATH, use_llm: bool = True) -> pd.DataFrame:
    """Pontua manchetes relevantes do arquivo (só as novas) e guarda em CSV. Devolve o cache completo."""
    import asyncio

    cache = load_cache(path)
    arch = archive[archive["symbol"] != "MARKET"].drop_duplicates(["symbol", "headline"])
    arch = arch[[is_relevant(r.symbol, r.headline) for r in arch.itertuples()]]
    done = set(zip(cache["symbol"], cache["headline"]))
    new = arch[[(s, h) not in done for s, h in zip(arch["symbol"], arch["headline"])]]
    if not new.empty:
        rows = pd.DataFrame({"symbol": new["symbol"].values, "headline": new["headline"].values})
        rows["lexicon"] = [lexicon_score(h) for h in rows["headline"]]
        llm = asyncio.run(llm_scores(list(zip(rows["symbol"], rows["headline"])))) if use_llm else [None] * len(rows)
        rows["llm"] = pd.Series(llm, dtype="float")
        cache = pd.concat([cache, rows], ignore_index=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        cache.to_csv(path, index=False)
    return cache
