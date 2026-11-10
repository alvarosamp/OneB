"""Thin async wrapper around the LLM APIs for the "explain, don't decide"
features: daily narrative summary, Q&A grounded in our own data, and
optional alert-message enrichment.

Supports three providers via LLM_PROVIDER in .env:
- "anthropic" (Claude) — recommended for production, paid.
- "gemini" — free tier via Google AI Studio, good for testing without a
  credit card. Same prompts, same behavior, just a different backend.
- "groq" — also free without a credit card, runs open models (Llama) very
  fast via an OpenAI-compatible API. Good fallback if Gemini's free tier
  account has issues (e.g. a suspended Google Cloud consumer project).

Design constraints (deliberate):
- Every function returns None (or a safe fallback) if the API key is missing
  or the call fails — callers always have a non-LLM fallback path, so an
  LLM outage never breaks the actual monitoring pipeline.
- Prompts explicitly instruct the model to use ONLY the data it's given and
  to say so when something isn't in that data, instead of guessing — this
  isn't a trading-decision engine, just a narrator over data we already
  collected ourselves.
- Every user-facing answer is expected to end with a plain-language
  reminder that this isn't investment advice (enforced via the system
  prompt, not just asked nicely) to stay consistent with the rest of the app.
"""
from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)

_DISCLAIMER_RULE = (
    "Nunca dê recomendação de compra/venda nem diga o que fazer — apenas descreva e explique "
    "os dados fornecidos. Se a pergunta pedir uma decisão de investimento, explique os dados "
    "relevantes e deixe claro que a decisão é do usuário."
)

_anthropic_client = None
_gemini_configured = False
_groq_client = None


def is_configured() -> bool:
    if settings.llm_provider == "gemini":
        return bool(settings.gemini_api_key)
    if settings.llm_provider == "groq":
        return bool(settings.groq_api_key)
    return bool(settings.anthropic_api_key)


def _get_anthropic_client():
    global _anthropic_client
    if not settings.anthropic_api_key:
        return None
    if _anthropic_client is None:
        from anthropic import AsyncAnthropic

        _anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


async def _call_anthropic(system_prompt: str, user_prompt: str, max_tokens: int) -> str | None:
    client = _get_anthropic_client()
    if client is None:
        return None
    try:
        response = await client.messages.create(
            model=settings.llm_model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        logger.exception("Falha ao chamar a API da Anthropic")
        return None


def _ensure_gemini_configured() -> bool:
    global _gemini_configured
    if not settings.gemini_api_key:
        return False
    if not _gemini_configured:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        _gemini_configured = True
    return True


async def _call_gemini(system_prompt: str, user_prompt: str, max_tokens: int) -> str | None:
    if not _ensure_gemini_configured():
        return None
    try:
        import google.generativeai as genai

        model = genai.GenerativeModel(settings.gemini_model, system_instruction=system_prompt)
        response = await model.generate_content_async(
            user_prompt,
            generation_config={"max_output_tokens": max_tokens},
        )
        return response.text.strip()
    except Exception:
        logger.exception("Falha ao chamar a API do Gemini")
        return None


def _get_groq_client():
    global _groq_client
    if not settings.groq_api_key:
        return None
    if _groq_client is None:
        from groq import AsyncGroq

        _groq_client = AsyncGroq(api_key=settings.groq_api_key)
    return _groq_client


async def _call_groq(system_prompt: str, user_prompt: str, max_tokens: int) -> str | None:
    client = _get_groq_client()
    if client is None:
        return None
    try:
        response = await client.chat.completions.create(
            model=settings.groq_model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception:
        logger.exception("Falha ao chamar a API da Groq")
        return None


async def _call(system_prompt: str, user_prompt: str, max_tokens: int = 500) -> str | None:
    if settings.llm_provider == "gemini":
        return await _call_gemini(system_prompt, user_prompt, max_tokens)
    if settings.llm_provider == "groq":
        return await _call_groq(system_prompt, user_prompt, max_tokens)
    return await _call_anthropic(system_prompt, user_prompt, max_tokens)


async def generate_daily_narrative(context: dict) -> str | None:
    """Turns the structured daily-summary data into a short narrative.

    `context` is a plain dict with the same data already assembled by
    app.scheduler.daily_summary (prices, news, econ events, earnings) — no
    extra DB/API calls happen here.
    """
    system_prompt = (
        "Você escreve um resumo diário de mercado em português, em 3 a 5 frases, curto e "
        "direto, para uma pessoa não-especialista que só quer entender o que aconteceu com "
        "os ativos que ela acompanha. Use SOMENTE os dados fornecidos no prompt do usuário — "
        "não invente preços, notícias ou eventos que não estejam lá. " + _DISCLAIMER_RULE
    )
    user_prompt = f"Dados do dia:\n{context}\n\nEscreva o resumo."
    return await _call(system_prompt, user_prompt, max_tokens=400)


async def generate_morning_narrative(context: dict) -> str | None:
    """Turns the structured morning-report data (indices, pivots, watchlist,
    news, calendar) into a short pre-market briefing, in the style of a
    trading-desk morning call.

    `context` is assembled by app.morning_report.build_report — no extra
    DB/API calls happen here.
    """
    system_prompt = (
        "Você escreve a análise matinal de pré-mercado de uma mesa de operações, em português, "
        "em formato de bullet points curtos organizados por seção (Nasdaq, S&P/NYSE, Ouro, "
        "Watchlist, Destaques do dia). Para cada índice/ativo, comente o viés do dia (alta/baixa/"
        "lateral) com base na variação e nos níveis de pivot (P, S1-S3, R1-R3) fornecidos — cite os "
        "níveis mais próximos do preço atual como suporte/resistência a observar. Use SOMENTE os "
        "dados fornecidos no prompt do usuário — não invente preços, notícias ou eventos que não "
        "estejam lá. " + _DISCLAIMER_RULE
    )
    user_prompt = f"Dados de pré-mercado de hoje:\n{context}\n\nEscreva a análise matinal."
    return await _call(system_prompt, user_prompt, max_tokens=700)


async def answer_question(question: str, context: dict, history: list[dict] | None = None) -> str:
    """Answers a free-text question grounded only in `context`.

    Always returns a string (never None) — if the LLM is unavailable, returns
    a clear message instead of silently failing, since this is a direct
    user-initiated request (chat/telegram), unlike the passive daily summary.
    """
    system_prompt = (
        "Você é um assistente em formato de chatbot para a OneB Market, uma plataforma de monitoramento de mercados. "
        "Responda usando SOMENTE os dados fornecidos no prompt (preços, notícias, alertas recentes "
        "e o pequeno histórico da conversa). Se a informação não estiver nos dados fornecidos, diga "
        "claramente que não tem esse dado disponível — não invente. Seja direto, mas ajude o usuário "
        "a investigar: quando fizer sentido, organize em 'Leitura', 'Pontos de atenção' e 'Próximo "
        "passo para validar'. " + _DISCLAIMER_RULE
    )
    if not is_configured():
        return (
            "O assistente de IA não está configurado (falta a API key do provedor escolhido em "
            "LLM_PROVIDER — ANTHROPIC_API_KEY, GEMINI_API_KEY ou GROQ_API_KEY — no .env). "
            "Peça pro administrador configurar."
        )

    recent_history = history or []
    user_prompt = (
        f"Dados disponíveis:\n{context}\n\n"
        f"Histórico recente da conversa:\n{recent_history}\n\n"
        f"Pergunta atual: {question}"
    )
    answer = await _call(system_prompt, user_prompt, max_tokens=600)
    return answer or "Não consegui gerar uma resposta agora (falha ao chamar a API de IA). Tente de novo em instantes."


async def generate_recommendation_thesis(context: dict) -> str | None:
    """Turns one already-computed rule-engine recommendation into a short narrative.

    The action, score, stop/target and historical memory are all decided by
    app.decision_engine before this is called — this only explains that
    reading in plain language, it never picks the action itself.
    """
    system_prompt = (
        "Você recebe a leitura já calculada por um motor de regras determinístico (ação, "
        "score, memória histórica de acerto/erro, stop e alvo) para um ativo acompanhado pela OneB Market. "
        "Escreva, em português, 2 a 3 frases explicando essa leitura para quem não é "
        "especialista: por que o motor chegou nessa ação e o que observar para validar ou "
        "invalidar a tese. Use SOMENTE os dados fornecidos no contexto — não invente preço, "
        "notícia ou fato que não esteja lá. Você está narrando uma decisão de regras já "
        "tomada, não tomando uma decisão nova. " + _DISCLAIMER_RULE
    )
    user_prompt = f"Leitura do motor de regras:\n{context}\n\nEscreva a narrativa."
    return await _call(system_prompt, user_prompt, max_tokens=220)


async def enrich_alert_message(base_message: str, market_data: dict) -> str | None:
    """Adds one short sentence of plain-language context to an already-generated
    alert message. Only called when settings.llm_enrich_alerts is True.
    """
    system_prompt = (
        "Você recebe uma mensagem de alerta técnico já pronta e adiciona, no máximo, uma "
        "frase curta de contexto em português explicando o que esse tipo de sinal costuma "
        "significar. Não repita a mensagem original, apenas complemente. Use só os dados "
        "fornecidos. " + _DISCLAIMER_RULE
    )
    user_prompt = f"Alerta: {base_message}\nDados de mercado: {market_data}"
    extra = await _call(system_prompt, user_prompt, max_tokens=120)
    if not extra:
        return None
    return f"{base_message}\n💡 {extra}"
