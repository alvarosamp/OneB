import logging
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Data providers
    finnhub_api_key: str = ""
    fmp_api_key: str = ""
    # "yfinance" (gratis/fallback) ou "tiingo" (recomendado para pesquisa EOD).
    market_data_provider: str = "yfinance"
    # Tiingo EOD (https://www.tiingo.com/documentation/end-of-day) - recomendado
    # para pesquisa/backtests porque fornece OHLCV ajustado e campos de split/dividendo.
    tiingo_api_key: str = ""
    # FRED (grátis em https://fred.stlouisfed.org/docs/api/api_key.html) - fonte oficial
    # para yields do Tesouro e dollar index, usada pelo regime engine em vez de proxies
    # via Yahoo (ver app/market_data/fred_client.py e app/market_data/macro_data.py).
    fred_api_key: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    # O bot não tem login próprio (é restrito por telegram_chat_id) — todos os comandos e os
    # jobs agendados que enviam mensagem (resumo diário, análise matinal) agem em nome desta
    # conta. Vazio = usa o primeiro admin cadastrado.
    telegram_acts_as_username: str = ""

    # Ambiente de execução ("development" ou "production"). Controla exigências de
    # segurança que não fazem sentido travar o dev local (ver SECRET_KEY abaixo e o
    # atributo "secure" do cookie de sessão em app/auth.py).
    environment: str = "development"

    # Auth (ver app/auth.py). Modelo de sessão em duas partes:
    #   - access token: JWT curto, devolvido no corpo da resposta e guardado APENAS em
    #     memória pelo SPA (nunca em localStorage — um XSS lê localStorage, não lê uma
    #     variável de módulo que morre no reload);
    #   - refresh token: string opaca de 30 dias, guardada com hash no banco e entregue
    #     num cookie httpOnly. É rotacionada a cada uso, com detecção de reuso.
    # Antes era um único JWT de 7 dias em localStorage: um XSS roubava uma credencial
    # válida por uma semana, sem nenhuma forma de revogar.
    secret_key: str = ""
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # Cookie httpOnly que carrega o refresh token. Path restrito a /api/auth porque é o
    # único lugar que precisa dele, e SameSite=strict + header obrigatório
    # (X-Refresh-Request) fecham o vetor de CSRF nas duas rotas que dependem do cookie.
    refresh_cookie_name: str = "oneb_refresh"

    # Bootstrap do admin inicial. Antes, o primeiro usuário a se cadastrar virava admin
    # automaticamente — qualquer visitante que chegasse primeiro no /cadastro ganhava
    # controle total (ver app/routers/auth.py). Cadastro público agora NUNCA concede
    # is_admin; se essas duas variáveis estiverem preenchidas no .env, esse usuário é
    # criado como admin no startup (app.auth.ensure_admin_bootstrap), somente se o banco
    # ainda não tiver nenhum usuário. Depois disso, promova outros com
    # `python -m scripts.promote_admin <usuario>`.
    admin_bootstrap_username: str = ""
    admin_bootstrap_password: str = ""

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
    macro_refresh_seconds: int = 900
    macro_intelligence_hour_utc: int = 23
    global_news_categories: str = "general,forex"
    calendar_refresh_hour_utc: int = 6
    radar_bot_hour_utc: int = 13
    weekly_review_bot_day_of_week: str = "fri"
    weekly_review_bot_hour_utc: int = 20
    run_embedded_scheduler: bool = True

    # Retreino do modelo probabilistico (app/probability_model.py) - semanal por padrao,
    # porque o treino usa 2 anos de historico e nao muda de forma significativa dia a dia.
    probability_model_retrain_day_of_week: str = "sun"
    probability_model_retrain_hour_utc: int = 5

    # Recalibracao walk-forward da estrategia (scripts/calibrate_decision_strategy.py) -
    # roda pouco antes do retreino do modelo probabilistico pra manter os dois em sincronia.
    decision_recalibration_day_of_week: str = "sun"
    decision_recalibration_hour_utc: int = 4

    # Registro diario da Mesa IA (decision desk) - grava as recomendacoes do dia como um
    # snapshot global (user_id nulo), construindo um historico real de acompanhamento
    # forward-tested em vez de depender de alguem clicar "Registrar leitura" manualmente.
    decision_desk_snapshot_hour_utc: int = 20

    # Governança operacional da Mesa IA. Com pouca evidência observada, ou
    # desempenho recente insuficiente, entradas viram observação.
    decision_health_min_samples: int = 20
    decision_health_min_win_rate_pct: float = 45.0

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
    if settings.environment == "production":
        # Em produção, uma SECRET_KEY ausente não deve degradar silenciosamente para uma
        # chave efêmera — ela derruba todas as sessões a cada restart/deploy e, pior, se
        # o processo tiver múltiplas réplicas cada uma gera a SUA própria chave, então um
        # token emitido por uma réplica é rejeitado pelas outras. Falha alto e cedo.
        raise RuntimeError(
            "SECRET_KEY não configurada no .env com ENVIRONMENT=production. Gere uma chave "
            "fixa com `python -c \"import secrets; print(secrets.token_hex(32))\"`, coloque "
            "em SECRET_KEY no .env e reinicie."
        )
    # Sem SECRET_KEY no .env: gera uma chave efêmera pra não travar o dev local, mas ela muda
    # a cada restart (derruba todas as sessões ativas) — inaceitável em produção (por isso o
    # bloco acima falha o boot quando ENVIRONMENT=production).
    settings.secret_key = secrets.token_hex(32)
    logger.warning(
        "SECRET_KEY não configurada no .env — usando uma chave temporária gerada agora. "
        "Isso invalida todos os tokens JWT emitidos a cada restart do servidor (todo mundo "
        "precisa logar de novo). Gere uma chave fixa com "
        "`python -c \"import secrets; print(secrets.token_hex(32))\"` e coloque em SECRET_KEY "
        "no .env antes de ir pra produção (com ENVIRONMENT=production)."
    )
