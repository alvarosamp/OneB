import logging
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Data providers
    finnhub_api_key: str = ""
    fmp_api_key: str = ""

    # SEC EDGAR exige identificação real (nome + e-mail) no User-Agent; só p/ scripts de pesquisa
    sec_user_agent: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Auth (JWT, ver app/auth.py)
    secret_key: str = ""
    jwt_expire_hours: int = 168  # 7 dias

    # CORS - origem do front-end React separado (Vite dev server por padrão)
    frontend_origin: str = "http://localhost:5173"

    # Database
    database_url: str = "sqlite:///./nasdaq_monitor.db"

    # Polling
    quote_poll_seconds: int = 60
    indicator_refresh_seconds: int = 300
    daily_summary_hour_utc: int = 21  # ~16:00 ET close wrap-up
    morning_report_hour_utc: int = 11  # ~07:00-08:00 ET, before market open
    news_refresh_seconds: int = 1800
    global_news_refresh_seconds: int = 900
    news_archive_seconds: int = 21600  # arquivo de manchetes p/ pesquisa (6h)
    global_news_categories: str = "general,forex"
    calendar_refresh_hour_utc: int = 6

    # Assistente com LLM - opcional, tudo degrada graciosamente sem a key configurada.
    # "anthropic" (produção, pago), "gemini" ou "groq" (ambos grátis, bons pra testar).
    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-4-5-20251001"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    llm_daily_narrative_enabled: bool = True
    llm_enrich_alerts: bool = False  # desligado por padrão pra controlar custo/volume


settings = Settings()

if not settings.secret_key:
    # Sem SECRET_KEY no .env: gera uma chave efêmera pra não travar o dev local, mas ela muda
    # a cada restart (derruba todas as sessões ativas) — inaceitável em produção.
    settings.secret_key = secrets.token_hex(32)
    logger.warning(
        "SECRET_KEY não configurada no .env — usando uma chave temporária gerada agora. "
        "Isso invalida todos os tokens JWT emitidos a cada restart do servidor (todo mundo "
        "precisa logar de novo). Gere uma chave fixa com "
        "`python -c \"import secrets; print(secrets.token_hex(32))\"` e coloque em SECRET_KEY "
        "no .env antes de ir pra produção."
    )
