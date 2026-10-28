"""Entende a pergunta sem LLM: qual ativo, que tipo de pergunta de risco, saldo e risco informados.

Usado pela resposta automática (sem LLM ou quando a API falha) para responder com as
ferramentas certas em vez de só listar o ledger. Perguntas sobre setup/oportunidade
continuam indo para o ledger.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

ASSET_WORDS = {
    "NAS100": ("nasdaq", "us100", "nas100", "nq", "ndx", "tech 100"),
    "SPX500": ("s&p", "sp500", "s&p500", "us500", "spx", "es=f", "sp 500"),
    "XAUUSD": ("ouro", "gold", "xau", "xauusd"),
    "EURUSD": ("euro", "eurusd", "eur/usd", "eur usd"),
}
# Pedido de entrada/alvo/recomendação é sobre setup: o ledger mostra o estado e recusa dar níveis.
SETUP_WORDS = ("setup", "fakeout", "oportunidade", "13x", "sinal", "ledger", "confirmacao", "invalidad", "estado",
               "entrada", "entrar", "alvo", "recomend", "replay")
INTENTS = {
    "sizing": ("quanto operar", "lote", "tamanho", "saldo minimo", "quanto preciso", "iniciante", "comecar", "comecando",
               "pouco dinheiro", "conta pequena", "capital minimo", "deposito minimo", "quantos contratos", "quanto posso", "quanto arrisc", "posicao", "alavanc",
               "arrisco", "arriscar", "gerenciamento"),
    "stop": ("stop", "stop loss", "onde paro"),
    "forecast": ("mexer", "volatil", "amplitude", "oscil", "movimento", "agitad", "calmo", "range", "andar", "vale a pena"),
    "hours": ("horario", "hora", "abertura", "agora e bom", "melhor hora", "quando operar", "que horas", "melhor momento", "janela",
              "vale a pena", "segunda", "terca", "quarta", "quinta", "sexta", "dia da semana"),
    "calendar": ("evento", "cpi", "fomc", "payroll", "nfp", "calendario", "inflacao", "fed", "juros"),
    "cost": ("custo", "custa", "spread", "caro", "barato", "taxa", "corretagem", "vale a pena"),
    "trend": ("tendencia", "subindo", "caindo", "em alta", "em baixa"),
    "direction": ("compro", "vendo", "comprar", "vender", "vai subir", "vai cair", "sobe ou desce", "entrar comprado", "entrar vendido",
                  "abrir em alta", "abrir em baixa", "fechar em alta", "fechar em baixa"),
    "briefing": ("hoje", " hj", "amanha", "o que esperar", "proximo pregao", "proxima sessao", "essa semana", "esta semana", "noticia", "mercado agora", "como esta o", "como ta o", "o que preciso saber", "resumo", "panorama",
                 "bom dia", "briefing", "visao geral", "o que esta acontecendo", "o que tem pra"),
    "compare": ("qual mexe mais", "qual mexe menos", "compar", "versus", " vs ", "ou o nasdaq", "ou o ouro", "qual e melhor", "qual o melhor ativo",
                "qual mais", "qual o mais", "mais barato", "mais caro"),
    "accuracy": ("acerta", "acertado", "acertou", "confiavel", "confiar", "funciona a previsao", "previsao funciona", "previsao de voces funciona",
                 "previsoes funcionam", "funciona mesmo", "taxa de acerto da", "placar"),
}


@dataclass
class Intent:
    assets: list[str] = field(default_factory=list)
    kinds: set[str] = field(default_factory=set)
    balance: float | None = None
    risk_pct: float | None = None
    currency_brl: bool = False
    question_norm: str = ""

    @property
    def is_risk_question(self) -> bool:
        return bool(self.kinds)


def _norm(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def _num(token: str) -> float | None:
    token = token.strip().rstrip(".,")
    if "," in token:
        token = token.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", token):
        token = token.replace(".", "")
    try:
        return float(token)
    except ValueError:
        return None


def money(question: str) -> tuple[float | None, float | None, bool]:
    """(saldo, risco %, saldo em reais?) citados na pergunta."""
    q = _norm(question)
    risk = re.search(r"(\d+(?:[.,]\d+)?)\s*%", q)
    risk_pct = _num(risk.group(1)) if risk else None
    balance, brl = None, False
    bal = re.search(r"(?:us\$|r\$|\$|saldo|conta|capital|banca)\D{0,15}?(\d[\d.,]*\d|\d)(\s*(?:mil|k)\b)?", q)
    if bal:
        balance = _num(bal.group(1))
        if balance is not None and bal.group(2):
            balance *= 1000
        brl = "r$" in q or "reais" in q
    else:
        bal = re.search(r"(\d[\d.,]*\d|\d)\s*(mil|k)?\s*(dolares|dolar|usd|reais|real)\b", q)
        if bal:
            balance = _num(bal.group(1))
            if balance is not None and bal.group(2):
                balance *= 1000
            brl = bal.group(3).startswith("rea")
    return balance, risk_pct, brl


def parse(question: str) -> Intent:
    q = _norm(question)
    intent = Intent(question_norm=q)
    if any(w in q for w in SETUP_WORDS):
        return intent  # pergunta de setup: o ledger responde
    for key, words in ASSET_WORDS.items():
        if any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", q) for w in words):
            intent.assets.append(key)
    for kind, words in INTENTS.items():
        if any(w in q for w in words):
            intent.kinds.add(kind)
    balance, risk_pct, brl = money(question)
    if risk_pct is not None:
        intent.risk_pct = risk_pct
    if balance is not None:
        intent.balance, intent.currency_brl = balance, brl
        intent.kinds.add("sizing")  # citou saldo: a pergunta é se dá para operar
    if intent.balance and intent.risk_pct:
        intent.kinds.add("sizing")
    return intent


SETUP_NAMES = {
    "gold_fakeout_open_v1": ("gold fakeout", "fakeout"),
    "x13_ex5_oos_dukascopy": ("13x",),
    "london_ex5_oos_dukascopy": ("london", "londres", "caixa de londres"),
    "pips100_ex5_oos_dukascopy": ("100 pips", "100pips"),
}
STATS_WORDS = ("performou", "desempenho", "replay", "resultado", "melhor que", "aleat", "estatistic", "funciona",
               "expectativa", "expectancia", "acerto", "taxa de acerto", "backtest", "deu certo")


def setup_stats_question(question: str) -> str | None:
    """Nome do setup quando a pergunta é sobre o desempenho dele (replay, acerto, contra aleatório)."""
    q = _norm(question)
    if any(w in q for w in ("melhor setup", "qual setup", "quais setups", "setups funcionam", "algum setup")):
        return "__all__"
    if not any(w in q for w in STATS_WORDS):
        return None
    for setup, words in SETUP_NAMES.items():
        if any(w in q for w in words):
            return setup
    return None


FOLLOW_UP_HINTS = ("e no", "e na", "e o ", "e a ", "e para", "e pro", "e pra", "e com", "e se", "e quanto", "mesma coisa", "e agora", "e amanha")


def resolve(question: str, history: list[dict] | None = None) -> Intent:
    """Intenção da pergunta, herdando da pergunta anterior do usuário o que faltar.

    "Quanto devo operar no Nasdaq? saldo US$ 2.000, risco 1%" seguido de "e no ouro?" vira
    lote no ouro com o mesmo saldo e risco. Pergunta de setup nunca herda (vai para o ledger).
    """
    current = parse(question)
    q = _norm(question)
    if any(w in q for w in SETUP_WORDS):
        return current
    previous = None
    for turn in reversed(history or []):
        if turn.get("role") == "user" and (turn.get("content") or turn.get("text")):
            previous = parse(str(turn.get("content") or turn.get("text")))
            break
    if previous is None or not previous.is_risk_question:
        return current
    follow_up = len(q.split()) <= 6 or any(q.startswith(h) or h in q for h in FOLLOW_UP_HINTS)
    if not follow_up and current.is_risk_question:
        return current
    if not current.kinds:
        current.kinds = set(previous.kinds)
    if not current.assets:
        current.assets = list(previous.assets)
    if current.balance is None and previous.balance is not None:
        current.balance, current.currency_brl = previous.balance, previous.currency_brl
    if current.risk_pct is None:
        current.risk_pct = previous.risk_pct
    if current.balance and current.risk_pct and current.kinds:
        current.kinds.add("sizing")
    return current


PLAN_LONG = ("se eu comprar", "se eu compro", "plano de compra", "plano para comprar", "plano comprado", "plano de trade de compra",
             "quero comprar", "vou comprar", "pensando em comprar", "pretendo comprar")
PLAN_SHORT = ("se eu vender", "se eu vendo", "plano de venda", "plano para vender", "plano vendido", "plano de trade de venda",
              "quero vender", "vou vender", "pensando em vender", "pretendo vender")
# "Compro ou vendo?" / "me dá entrada, stop e alvo": o usuário quer a direção, que o OneB não dá.
PLAN_DIRECTION = ("compro ou vendo", "compra ou venda", "comprar ou vender", "compro ou vendo", "entrada, stop", "entrada stop",
                  "me da entrada", "me de entrada", "qual a entrada", "qual entrada", "sinal de entrada", "me da um sinal", "qual a direcao",
                  "sobe ou desce", "vai subir ou cair", "vai subir ou descer", "me manda um sinal", "manda um sinal", "manda sinal",
                  "me passa um sinal", "tem sinal", "algum sinal", "sinal de compra", "sinal de venda", "um sinal de", "da um sinal",
                  "bom pra entrar", "bom para entrar", "hora de entrar", "devo entrar", "posso entrar", "vale entrar", "bom pra comprar",
                  "bom pra vender", "bom para comprar", "bom para vender", "devo comprar", "devo vender")
PLAN_ODDS = ("probabilidade", "mais chance", "chance de bater", "chance de atingir", "chance do alvo", "chance de dar")


def plan_request(question: str) -> tuple[str, str] | None:
    """(ativo, direção) quando o usuário pede um plano para a direção que ELE escolheu; senão None."""
    q = _norm(question)
    direction = "long" if any(w in q for w in PLAN_LONG) else "short" if any(w in q for w in PLAN_SHORT) else None
    if direction is None and any(w in q for w in PLAN_DIRECTION):
        direction = "pick"  # pediu a direção (sem escolher uma): plano dos dois lados + o teste das regras de direção
    if direction is None and any(w in q for w in PLAN_ODDS):
        direction = "both"  # chance de bater alvo sem direção escolhida: mostra compra e venda
    if direction is None:
        return None
    for key, words in ASSET_WORDS.items():
        if any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", q) for w in words):
            return key, direction
    if direction in ("both", "pick"):
        return "__main__", direction  # sem ativo: responde para Nasdaq e ouro
    return None


RETURN_WORDS = ("quanto ganho", "quanto vou ganhar", "quanto da pra ganhar", "quanto da para ganhar", "quanto rende",
                "ganho por mes", "ganhar por mes", "lucro por mes", "renda por mes", "garante lucro", "garantem lucro", "garantia de lucro",
                "lucro garantido", "ganho garantido", "ficar rico", "renda extra", "viver de trade", "retorno mensal")


def returns_question(question: str) -> bool:
    """Pergunta sobre ganho esperado ou garantia de lucro."""
    q = _norm(question)
    return any(w in q for w in RETURN_WORDS)


PLAN_LIVE_WORDS = ("plano das 10", "plano das dez", "plano bateu", "planos bateram", "plano de hoje", "planos de hoje", "plano do dia", "placar do plano", "placar de hoje", "placar ao vivo",
                   "bateu o alvo", "bateu alvo", "bateu o stop", "como foi o plano", "resultado do plano", "plano de ontem")


LEDGER_WORDS = SETUP_WORDS + ("mudou", "mudanca", "ultimos", "minutos", "monitorad", "acompanhando", "ativo agora", "em aberto")


def ledger_question(question: str) -> bool:
    """Pergunta sobre setups, oportunidades e o que mudou: o ledger responde."""
    q = _norm(question)
    return any(w in q for w in LEDGER_WORDS)


def plan_live_question(question: str) -> bool:
    q = _norm(question)
    return any(w in q for w in PLAN_LIVE_WORDS)


ILLUSION_WORDS = ("assertividade", "vtx", "vortex", "taxa de acerto", "acerto de 8", "acerto de 9", "acerta 8", "acerta 9",
                  "% de acerto", "servico de sinais", "sinais com", "win rate", "winrate")


def win_rate_question(question: str) -> bool:
    """Pergunta sobre taxa de acerto anunciada / serviço de sinais (e não sobre um setup específico)."""
    q = _norm(question)
    return any(w in q for w in ILLUSION_WORDS) and not any(w in q for words in SETUP_NAMES.values() for w in words)
