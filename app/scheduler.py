from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

from app.config import settings
from app.db import SessionLocal
from app.dedup import filter_new_by_key
from app.market_data import finnhub_client, fred_client
from app.market_data import service as market_data_service
from app.models import (
    AlertLog,
    AlertRule,
    EarningsEvent,
    EconomicEvent,
    GlobalNewsItem,
    NewsItem,
    PriceSnapshot,
    WatchlistItem,
)
from app.rules_engine import MarketState, RuleContext, cooldown_expired, evaluate_conditions
from app.telegram_bot import resolve_acting_user_id, send_alert

logger = logging.getLogger(__name__)


async def poll_quotes() -> None:
    db = SessionLocal()
    try:
        items = db.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).all()
        for item in items:
            quote = finnhub_client.get_quote(item.symbol)
            if quote is None:
                continue
            db.add(
                PriceSnapshot(
                    watchlist_item_id=item.id,
                    price=quote.price,
                    change_pct=quote.change_pct,
                    volume=quote.volume,
                )
            )
        db.commit()
    except Exception:
        logger.exception("Erro no job poll_quotes")
        db.rollback()
    finally:
        db.close()


async def evaluate_rules(telegram_app: Application | None) -> None:
    db = SessionLocal()
    try:
        items = db.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).all()
        for item in items:
            rules = db.query(AlertRule).filter(
                AlertRule.watchlist_item_id == item.id, AlertRule.active.is_(True)
            ).all()
            if not rules:
                continue

            latest_snapshot = (
                db.query(PriceSnapshot)
                .filter(PriceSnapshot.watchlist_item_id == item.id)
                .order_by(PriceSnapshot.taken_at.desc())
                .first()
            )
            if latest_snapshot is None:
                continue

            history = market_data_service.get_bars(item.symbol)
            if history.empty:
                continue

            state = MarketState(
                symbol=item.symbol,
                price=latest_snapshot.price,
                change_pct=latest_snapshot.change_pct,
                volume=latest_snapshot.volume,
                history=history,
            )

            for rule in rules:
                if not cooldown_expired(rule.last_triggered_at, rule.cooldown_minutes):
                    continue
                if not rule.conditions:
                    continue
                contexts = [
                    RuleContext(
                        rule_type=cond.rule_type,
                        threshold=cond.threshold,
                        param_a=cond.param_a,
                        param_b=cond.param_b,
                    )
                    for cond in rule.conditions
                ]
                result = evaluate_conditions(contexts, rule.logic, state)
                if not result.triggered:
                    continue

                from app.models import utcnow

                rule.last_triggered_at = utcnow()
                rule_type_label = "+".join(cond.rule_type.value for cond in rule.conditions)
                message = result.message

                if settings.llm_enrich_alerts:
                    from app.llm_client import enrich_alert_message

                    enriched = await enrich_alert_message(
                        message,
                        {"symbol": item.symbol, "price": state.price, "change_pct": state.change_pct},
                    )
                    if enriched:
                        message = enriched

                log = AlertLog(user_id=item.user_id, symbol=item.symbol, rule_type=rule_type_label, message=message)
                db.add(log)
                db.commit()

                delivered = await send_alert(telegram_app, f"🔔 {message}")
                log.delivered_telegram = delivered
                db.commit()
    except Exception:
        logger.exception("Erro no job evaluate_rules")
        db.rollback()
    finally:
        db.close()


async def refresh_news() -> None:
    db = SessionLocal()
    try:
        items = db.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).all()
        today = date.today()
        week_ago = today - timedelta(days=7)
        existing_urls = {u for (u,) in db.query(NewsItem.url).all()}

        for item in items:
            articles = finnhub_client.get_company_news(item.symbol, week_ago, today)
            new_articles = filter_new_by_key(articles, existing_urls, key_fn=lambda a: a.url)
            for article in new_articles:
                db.add(
                    NewsItem(
                        symbol=article.symbol,
                        headline=article.headline,
                        summary=article.summary,
                        url=article.url,
                        source=article.source,
                        published_at=article.published_at,
                    )
                )
                existing_urls.add(article.url)
        db.commit()
    except Exception:
        logger.exception("Erro no job refresh_news")
        db.rollback()
    finally:
        db.close()


async def refresh_global_news() -> None:
    db = SessionLocal()
    try:
        categories = [c.strip() for c in settings.global_news_categories.split(",") if c.strip()]
        existing_urls = {u for (u,) in db.query(GlobalNewsItem.url).all()}

        for category in categories:
            articles = finnhub_client.get_market_news(category, limit=40)
            new_articles = filter_new_by_key(articles, existing_urls, key_fn=lambda a: a.url)
            for article in new_articles:
                db.add(
                    GlobalNewsItem(
                        category=category,
                        headline=article.headline,
                        summary=article.summary,
                        url=article.url,
                        source=article.source,
                        impact_score=finnhub_client.estimate_news_impact(article.headline, article.summary),
                        published_at=article.published_at,
                    )
                )
                existing_urls.add(article.url)
        db.commit()
    except Exception:
        logger.exception("Erro no job refresh_global_news")
        db.rollback()
    finally:
        db.close()


async def refresh_macro_snapshots() -> None:
    from app import regime_engine

    db = SessionLocal()
    try:
        stored = regime_engine.store_macro_snapshots(db)
        logger.info("Snapshot macro atualizado: %s instrumento(s).", stored)
    except Exception:
        logger.exception("Erro no job refresh_macro_snapshots")
        db.rollback()
    finally:
        db.close()


async def refresh_macro_intelligence() -> None:
    from app import regime_engine

    db = SessionLocal()
    try:
        snapshot = regime_engine.store_macro_intelligence_snapshot(db, refresh=True)
        logger.info(
            "Inteligencia macro diaria atualizada: %s (cobertura %.1f%%, frescos %s).",
            snapshot.snapshot_date,
            snapshot.coverage_pct,
            snapshot.fresh_count,
        )
    except Exception:
        logger.exception("Erro no job refresh_macro_intelligence")
        db.rollback()
    finally:
        db.close()


async def refresh_calendars() -> None:
    db = SessionLocal()
    try:
        today = date.today()

        econ_events = fred_client.get_economic_calendar(today, today + timedelta(days=7))
        existing_econ_keys = {
            (name, country, dt) for name, country, dt in db.query(
                EconomicEvent.event_name, EconomicEvent.country, EconomicEvent.event_date
            ).all()
        }
        new_econ = filter_new_by_key(
            econ_events, existing_econ_keys, key_fn=lambda e: (e.event_name, e.country, e.event_date)
        )
        for event in new_econ:
            db.add(
                EconomicEvent(
                    event_name=event.event_name,
                    country=event.country,
                    event_date=event.event_date,
                    impact=event.impact,
                    actual=event.actual,
                    forecast=event.forecast,
                    previous=event.previous,
                )
            )

        items = db.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).all()
        existing_earnings_keys = {
            (sym, dt) for sym, dt in db.query(EarningsEvent.symbol, EarningsEvent.event_date).all()
        }
        for item in items:
            earnings = finnhub_client.get_earnings_calendar(
                today, today + timedelta(days=14), symbol=item.symbol
            )
            new_earnings = filter_new_by_key(
                earnings, existing_earnings_keys, key_fn=lambda e: (e.symbol, e.event_date)
            )
            for entry in new_earnings:
                db.add(
                    EarningsEvent(
                        symbol=entry.symbol,
                        event_date=entry.event_date,
                        eps_estimate=entry.eps_estimate,
                        revenue_estimate=entry.revenue_estimate,
                    )
                )
                existing_earnings_keys.add((entry.symbol, entry.event_date))

        db.commit()
    except Exception:
        logger.exception("Erro no job refresh_calendars")
        db.rollback()
    finally:
        db.close()


async def daily_summary(telegram_app: Application | None) -> None:
    db = SessionLocal()
    try:
        user_id = resolve_acting_user_id(db)
        if user_id is None:
            return
        items = db.query(WatchlistItem).filter(WatchlistItem.user_id == user_id, WatchlistItem.active.is_(True)).all()
        if not items:
            return

        now = datetime.now(timezone.utc)
        prices = []
        lines = ["📊 Resumo do dia:"]
        for item in items:
            snap = (
                db.query(PriceSnapshot)
                .filter(PriceSnapshot.watchlist_item_id == item.id)
                .order_by(PriceSnapshot.taken_at.desc())
                .first()
            )
            if snap:
                arrow = "🔺" if snap.change_pct >= 0 else "🔻"
                lines.append(f"{item.symbol}: {snap.price:.2f} {arrow} {snap.change_pct:+.2f}%")
                prices.append({"symbol": item.symbol, "price": snap.price, "change_pct": snap.change_pct})

        since = now - timedelta(hours=24)
        news = (
            db.query(NewsItem)
            .filter(NewsItem.published_at >= since)
            .order_by(NewsItem.published_at.desc())
            .limit(5)
            .all()
        )
        if news:
            lines.append("\n📰 Notícias das últimas 24h:")
            lines.extend(f"• {n.symbol}: {n.headline}" for n in news)
        news_data = [{"symbol": n.symbol, "headline": n.headline} for n in news]

        global_news = (
            db.query(GlobalNewsItem)
            .filter(GlobalNewsItem.published_at >= since)
            .order_by(GlobalNewsItem.impact_score.desc(), GlobalNewsItem.published_at.desc())
            .limit(5)
            .all()
        )
        if global_news:
            lines.append("\nNoticias globais de maior impacto:")
            lines.extend(f"- {n.headline} ({n.source or n.category}, impacto {n.impact_score})" for n in global_news)
        global_news_data = [
            {"headline": n.headline, "source": n.source, "impact_score": n.impact_score} for n in global_news
        ]

        econ_today = (
            db.query(EconomicEvent)
            .filter(
                EconomicEvent.event_date >= now.replace(hour=0, minute=0, second=0, microsecond=0),
                EconomicEvent.event_date < now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
                EconomicEvent.impact == "high",
            )
            .all()
        )
        if econ_today:
            lines.append("\n🌎 Eventos econômicos de alto impacto hoje:")
            lines.extend(f"• {e.event_name} ({e.country})" for e in econ_today)
        econ_data = [{"event_name": e.event_name, "country": e.country} for e in econ_today]

        upcoming_earnings = (
            db.query(EarningsEvent)
            .filter(EarningsEvent.event_date >= now, EarningsEvent.event_date <= now + timedelta(days=7))
            .order_by(EarningsEvent.event_date)
            .all()
        )
        if upcoming_earnings:
            lines.append("\n📅 Earnings da watchlist nos próximos 7 dias:")
            lines.extend(f"• {e.symbol}: {e.event_date.strftime('%d/%m')}" for e in upcoming_earnings)
        earnings_data = [{"symbol": e.symbol, "date": e.event_date.strftime("%d/%m")} for e in upcoming_earnings]

        message = "\n".join(lines)

        if settings.llm_daily_narrative_enabled:
            from app.llm_client import generate_daily_narrative

            narrative = await generate_daily_narrative(
                {
                    "precos": prices,
                    "noticias_24h": news_data,
                    "noticias_globais_24h": global_news_data,
                    "eventos_economicos_alto_impacto_hoje": econ_data,
                    "earnings_proximos_7_dias": earnings_data,
                }
            )
            if narrative:
                message = f"📊 Resumo do dia:\n{narrative}"

        await send_alert(telegram_app, message)
    finally:
        db.close()


async def radar_bot_summary(telegram_app: Application | None) -> None:
    from app.bots import radar_bot

    db = SessionLocal()
    try:
        await send_alert(telegram_app, radar_bot(db).body)
    finally:
        db.close()


async def morning_report_job(telegram_app: Application | None) -> None:
    from app import morning_report

    db = SessionLocal()
    try:
        user_id = resolve_acting_user_id(db)
        if user_id is None:
            return
        report = await morning_report.generate_and_store(db, user_id)
        delivered = await send_alert(telegram_app, f"☀️ {report.narrative}")
        report.delivered_telegram = delivered
        db.commit()
    except Exception:
        logger.exception("Erro no job morning_report")
        db.rollback()
    finally:
        db.close()


async def weekly_review_bot(telegram_app: Application | None) -> None:
    from app.bots import review_bot

    db = SessionLocal()
    try:
        await send_alert(telegram_app, review_bot(db).body)
    finally:
        db.close()


async def record_decision_desk_snapshot() -> None:
    """Runs the Mesa IA decision desk once a day as a global snapshot
    (user_id=None) and records it — this is what turns the reliability
    scoreboard into a real forward-tested track record over weeks instead of
    only whatever a person happened to click "Registrar leitura" on.
    """
    from app.decision_engine import build_decision_desk

    db = SessionLocal()
    try:
        result = await build_decision_desk(db, None, record=True)
        logger.info(
            "Snapshot diario da Mesa IA registrado: %s recomendacoes (%s).",
            result.get("recorded"),
            result.get("headline"),
        )
    except Exception:
        logger.exception("Falha ao registrar o snapshot diario da Mesa IA.")
    finally:
        db.close()


async def retrain_probability_model() -> None:
    """Weekly refresh for app/probability_model.py — walk-forward retrain on
    the latest 2 years of data, then swap the in-memory model used by
    app.decision_engine. Runs the (CPU/network-bound, synchronous) training
    script in a worker thread so it never blocks the event loop; any failure
    just leaves the previous model in place (decision desk keeps working).
    """
    from app import probability_model as pm
    from scripts import train_probability_model

    try:
        await asyncio.to_thread(train_probability_model.main)
        pm.reload_model()
        logger.info("Modelo probabilístico retreinado com sucesso.")
    except Exception:
        logger.exception("Falha ao retreinar o modelo probabilístico — mantendo o modelo anterior.")


async def recalibrate_decision_strategy() -> None:
    """Weekly walk-forward recalibration (scripts/calibrate_decision_strategy.py)
    for the live decision engine's thresholds — see app.decision_engine
    reload_calibration(). Runs before retrain_probability_model so both stay
    in sync on roughly the same data window. Same fail-open pattern: on
    failure, the decision desk keeps using whatever calibration (or static
    defaults) it already had.
    """
    from app import decision_engine
    from scripts import calibrate_decision_strategy

    try:
        await asyncio.to_thread(calibrate_decision_strategy.main)
        decision_engine.reload_calibration()
        logger.info("Recalibração walk-forward da estratégia (compra) concluída.")
    except Exception:
        logger.exception("Falha na recalibração walk-forward de compra — mantendo a calibração anterior.")

    try:
        from scripts import backtest_short_strategy

        await asyncio.to_thread(backtest_short_strategy.main)
        decision_engine.reload_short_calibration()
        logger.info("Recalibração walk-forward da estratégia (venda) concluída.")
    except Exception:
        logger.exception("Falha na recalibração walk-forward de venda — mantendo a calibração anterior.")


def build_scheduler(telegram_app: Application | None) -> AsyncIOScheduler:
    # job_defaults valem para TODOS os jobs registrados abaixo:
    #   max_instances=1  -> um job lento (ex.: coleta de cotacoes travada numa API)
    #                       nunca roda concorrente consigo mesmo no proximo tick;
    #   coalesce=True    -> se varios disparos ficaram atrasados (processo dormindo,
    #                       deploy, GC longo), roda UMA vez em vez de N vezes em rajada,
    #                       o que evitava tanto alerta duplicado quanto rajada de quota;
    #   misfire_grace_time -> disparo atrasado alem disso e descartado em vez de rodar
    #                       tarde com dado ja irrelevante.
    # Obs: isso resolve concorrencia DENTRO de um scheduler. Duas instancias do worker
    # rodando ao mesmo tempo continuam duplicando efeitos -- isso exige lease distribuido
    # e idempotencia por evento, ainda nao implementados.
    scheduler = AsyncIOScheduler(
        job_defaults={"max_instances": 1, "coalesce": True, "misfire_grace_time": 60}
    )
    scheduler.add_job(poll_quotes, "interval", seconds=settings.quote_poll_seconds, id="poll_quotes")
    scheduler.add_job(
        evaluate_rules,
        "interval",
        seconds=settings.indicator_refresh_seconds,
        args=[telegram_app],
        id="evaluate_rules",
    )
    scheduler.add_job(
        daily_summary,
        "cron",
        hour=settings.daily_summary_hour_utc,
        minute=0,
        args=[telegram_app],
        id="daily_summary",
    )
    scheduler.add_job(
        radar_bot_summary,
        "cron",
        hour=settings.radar_bot_hour_utc,
        minute=0,
        args=[telegram_app],
        id="radar_bot_summary",
    )
    scheduler.add_job(
        weekly_review_bot,
        "cron",
        day_of_week=settings.weekly_review_bot_day_of_week,
        hour=settings.weekly_review_bot_hour_utc,
        minute=0,
        args=[telegram_app],
        id="weekly_review_bot",
    )
    scheduler.add_job(
        morning_report_job,
        "cron",
        hour=settings.morning_report_hour_utc,
        minute=0,
        day_of_week="mon-fri",
        args=[telegram_app],
        id="morning_report",
    )
    scheduler.add_job(refresh_news, "interval", seconds=settings.news_refresh_seconds, id="refresh_news")
    scheduler.add_job(
        refresh_global_news,
        "interval",
        seconds=settings.global_news_refresh_seconds,
        next_run_time=datetime.now(timezone.utc),
        id="refresh_global_news",
    )
    scheduler.add_job(
        refresh_macro_snapshots,
        "interval",
        seconds=settings.macro_refresh_seconds,
        next_run_time=datetime.now(timezone.utc),
        id="refresh_macro_snapshots",
    )
    scheduler.add_job(
        refresh_macro_intelligence,
        "cron",
        day_of_week="mon-fri",
        hour=settings.macro_intelligence_hour_utc,
        minute=0,
        id="refresh_macro_intelligence",
    )
    scheduler.add_job(
        refresh_calendars,
        "cron",
        hour=settings.calendar_refresh_hour_utc,
        minute=0,
        id="refresh_calendars",
    )
    scheduler.add_job(
        retrain_probability_model,
        "cron",
        day_of_week=settings.probability_model_retrain_day_of_week,
        hour=settings.probability_model_retrain_hour_utc,
        minute=0,
        id="retrain_probability_model",
    )
    scheduler.add_job(
        recalibrate_decision_strategy,
        "cron",
        day_of_week=settings.decision_recalibration_day_of_week,
        hour=settings.decision_recalibration_hour_utc,
        minute=0,
        id="recalibrate_decision_strategy",
    )
    scheduler.add_job(
        record_decision_desk_snapshot,
        "cron",
        hour=settings.decision_desk_snapshot_hour_utc,
        minute=30,
        id="record_decision_desk_snapshot",
    )
    return scheduler
