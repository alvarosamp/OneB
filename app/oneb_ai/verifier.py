"""Verificador de grounding determinístico (plano Fase 4), aplicado DEPOIS da LLM.

Regras:
1. Todo número relevante da resposta precisa existir (com tolerância de
   arredondamento) em algum resultado de ferramenta desta conversa.
2. Todo claim precisa citar evidence_id/result_id que existam nesses resultados.
3. Sem oportunidade PAPER/LIVE_MANUAL nos resultados, é proibido linguagem de
   ordem ("compre agora", "abra posição"...).
"""
from __future__ import annotations

import re
import unicodedata

ACTIONABLE = {"PAPER", "LIVE_MANUAL"}
ORDER_PATTERNS = [
    r"\bcompre\b", r"\bvenda agora\b", r"\bvenda j[aá]\b", r"\bentre (comprado|vendido)\b", r"\babra (uma )?posi[cç][aã]o\b",
    r"\bcomprar agora\b", r"\bvender agora\b", r"\bpode entrar\b", r"\bentrada recomendada\b",
]
_NUMBER = re.compile(r"(?<![\w.])[-+−]?\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?(?![\w])|(?<![\w.])[-+−]?\d+(?:[.,]\d+)?(?![\w])")
_SKIP_PATTERNS = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ][\d:.+\-Z]+)?"),  # datas ISO
    re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b"),  # horários
    re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b"),  # datas dd/mm
    re.compile(r"\bMM\s?\d+\b|\bM\d{1,2}\b|\bH\d\b", re.I),  # nomes de média/timeframe
    re.compile(r"\b(?:confirma[cç][aã]o|confirmation)\s*\d\b", re.I),
    re.compile(r"(?:nasdaq|s&p|dow|ftse|dax|nikkei|russell|ibovespa)\s?-?\d{2,4}\b", re.I),  # nomes de índice (Nasdaq 100, S&P 500)
]


def _normalize(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def _parse_number(token: str) -> float | None:
    token = token.replace("−", "-").replace(" ", "")
    if "," in token:
        token = token.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"[-+]?\d{1,3}(\.\d{3})+", token):
        token = token.replace(".", "")
    try:
        return float(token)
    except ValueError:
        return None


def extract_numbers(text: str) -> list[float]:
    cleaned = text
    for pattern in _SKIP_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    out = []
    for match in _NUMBER.finditer(cleaned):
        value = _parse_number(match.group())
        if value is None:
            continue
        # Inteiros pequenos (contagens, "2 confirmações", "3 sinais") e anos não são afirmações numéricas de mercado.
        if value.is_integer() and (abs(value) <= 12 or 1990 <= value <= 2100):
            continue
        out.append(value)
    return out


def collect_source_numbers(obj, out: set[float] | None = None) -> set[float]:
    out = out if out is not None else set()
    if isinstance(obj, bool) or obj is None:
        return out
    if isinstance(obj, (int, float)):
        out.add(float(obj))
    elif isinstance(obj, str):
        out.update(extract_numbers(obj))
    elif isinstance(obj, dict):
        for value in obj.values():
            collect_source_numbers(value, out)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            collect_source_numbers(value, out)
    return out


def collect_ids(obj, out: set[str] | None = None) -> set[str]:
    out = out if out is not None else set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in ("evidence_id", "result_id", "opportunity_id") and isinstance(value, str):
                out.add(value)
            collect_ids(value, out)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            collect_ids(value, out)
    return out


def _grounded(value: float, sources: set[float]) -> bool:
    candidates = {value, abs(value)}
    # A resposta pode mostrar fração como % (0.352 -> 35,2%) ou o contrário.
    candidates |= {value / 100, abs(value) / 100, value * 100}
    for source in sources:
        for c in candidates:
            tolerance = max(0.011, abs(source) * 0.005)
            rounded_tenths = abs(c - round(source, 1)) <= 0.051
            rounded_units = abs(source) >= 100 and abs(c - round(source, 0)) <= 0.51  # preços citados sem centavos
            if abs(c - source) <= tolerance or rounded_tenths or rounded_units:
                return True
    return False


def answer_texts(answer: dict) -> list[str]:
    texts = [answer.get("headline", ""), answer.get("conclusion", "")]
    texts += [c.get("text", "") for c in answer.get("claims", [])]
    texts += [c.get("text", "") for c in answer.get("counter_points", [])]
    texts += list(answer.get("what_changed", []))
    return [t for t in texts if t]


def verify(answer: dict, tool_results: list[dict]) -> dict:
    sources = collect_source_numbers(tool_results)
    ids = collect_ids(tool_results)
    violations: list[dict] = []

    for text in answer_texts(answer):
        for value in extract_numbers(text):
            if not _grounded(value, sources):
                violations.append({"code": "UNGROUNDED_NUMBER", "value": value, "text": text[:160]})

    for group in ("claims", "counter_points"):
        for claim in answer.get(group, []):
            cited = claim.get("evidence_ids") or []
            if not cited:
                violations.append({"code": "CLAIM_WITHOUT_EVIDENCE", "text": claim.get("text", "")[:160]})
            for evidence_id in cited:
                if evidence_id not in ids:
                    violations.append({"code": "UNKNOWN_EVIDENCE_ID", "evidence_id": evidence_id})

    approvals = {o.get("approval") for r in tool_results for o in (r.get("opportunities") or []) if isinstance(o, dict)}
    if not approvals & ACTIONABLE:
        joined = _normalize(" ".join(answer_texts(answer)))
        for pattern in ORDER_PATTERNS:
            if re.search(pattern, joined):
                violations.append({"code": "ORDER_LANGUAGE_WITHOUT_APPROVAL", "pattern": pattern})

    if not tool_results:
        violations.append({"code": "NO_TOOLS_USED"})
    return {"ok": not violations, "violations": violations, "numbers_checked": sum(len(extract_numbers(t)) for t in answer_texts(answer))}
