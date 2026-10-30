from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

from app.config import settings
from app.db import SessionLocal
from app.dedup import filter_new_by_key
from app.market_data import finnhub_client, fmp_client, rss_news, yfinance_client
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
from app.telegram_bot import send_alert

logger = logging.getLogger(__name__)


def _company_news(symbol: str, from_date: date, to_date: date):
    """Finnhub quando há chave; RSS público (Yahoo) como fallback sem chave ou se vier vazio."""
    articles = finnhub_client.get_company_news(symbol, from_date, to_date) if settings.finnhub_api_key else []
    return articles or rss_news.get_company_news(symbol)


def _market_news(category: str, limit: int):
    articles = finnhub_client.get_market_news(category, limit=limit) if settings.finnhub_api_key else []
    return articles or rss_news.get_market_news(category, limit=limit)


async def poll_quotes() -> None:
    db = SessionLocal()
    try:
        items = db.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).all()
        for item in items:
            quote = finnhub_client.get_quote(item.symbol) if settings.finnhub_api_key else None
            if quote is None:
                quote = yfinance_client.get_quote(item.symbol)
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

            history = yfinance_client.get_history(item.symbol)
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

                log = AlertLog(symbol=item.symbol, rule_type=rule_type_label, message=message)
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
            articles = _company_news(item.symbol, week_ago, today)
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
            articles = _market_news(category, limit=40)
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


async def refresh_calendars() -> None:
    db = SessionLocal()
    try:
        today = date.today()

        econ_events = fmp_client.get_economic_calendar(today, today + timedelta(days=7))
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
        for item in items if settings.finnhub_api_key else []:
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
        items = db.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).all()
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


async def morning_report_job(telegram_app: Application | None) -> None:
    from app import morning_report

    db = SessionLocal()
    try:
        report = await morning_report.generate_and_store(db)
        delivered = await send_alert(telegram_app, f"☀️ {report.narrative}")
        report.delivered_telegram = delivered
        db.commit()
    except Exception:
        logger.exception("Erro no job morning_report")
        db.rollback()
    finally:
        db.close()


async def archive_news() -> None:
    """Guarda manchetes em disco para formar histórico de pesquisa (watchlist + ativos estudados)."""
    from app.research import news_archive

    db = SessionLocal()
    try:
        watch = [w.symbol for w in db.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).all()]
    finally:
        db.close()
    symbols = list(dict.fromkeys(watch + news_archive.research_symbols()))
    try:
        stats = await asyncio.to_thread(news_archive.collect, symbols)
        logger.info("Arquivo de manchetes: %s", stats)
    except Exception:
        logger.exception("Erro no job archive_news")


async def refresh_all() -> None:
    """Atualiza cotações, notícias e calendários agora (usado no startup e no botão "Atualizar")."""
    await poll_quotes()
    await refresh_news()
    await refresh_global_news()
    await refresh_calendars()


def build_scheduler(telegram_app: Application | None) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    # next_run_time=agora: sem isso o 1º ciclo só rodava após o intervalo inteiro (ex: notícias
    # por ativo esperavam 30 min), deixando o painel vazio logo após subir o servidor.
    now = datetime.now(timezone.utc)
    scheduler.add_job(
        poll_quotes, "interval", seconds=settings.quote_poll_seconds, next_run_time=now, id="poll_quotes"
    )
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
        morning_report_job,
        "cron",
        hour=settings.morning_report_hour_utc,
        minute=0,
        day_of_week="mon-fri",
        args=[telegram_app],
        id="morning_report",
    )
    scheduler.add_job(
        refresh_news, "interval", seconds=settings.news_refresh_seconds, next_run_time=now, id="refresh_news"
    )
    scheduler.add_job(
        refresh_global_news,
        "interval",
        seconds=settings.global_news_refresh_seconds,
        next_run_time=now,
        id="refresh_global_news",
    )
    scheduler.add_job(
        refresh_calendars,
        "cron",
        hour=settings.calendar_refresh_hour_utc,
        minute=0,
        id="refresh_calendars",
    )
    scheduler.add_job(
        archive_news, "interval", seconds=settings.news_archive_seconds, next_run_time=now, id="archive_news"
    )
    scheduler.add_job(refresh_calendars, "date", run_date=now, id="refresh_calendars_startup")
    return scheduler
