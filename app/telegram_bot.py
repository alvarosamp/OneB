"""Telegram bot: sends alerts and lets the authorized user manage the watchlist.

Restricted to a single whitelisted chat id (settings.telegram_chat_id) so a
stranger who finds the bot username can't read/alter the watchlist.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from telegram import InputFile, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import settings
from app.db import SessionLocal
from app.models import DecisionJournal, User, WatchlistItem

logger = logging.getLogger(__name__)


def resolve_acting_user_id(db: Session) -> int | None:
    """The Telegram bot and scheduled Telegram jobs have no login of their own
    (they're gated by a single whitelisted chat id, not a JWT session), so they
    act on behalf of one designated account — set via TELEGRAM_ACTS_AS_USERNAME,
    falling back to the first admin ever created. Returns None if no user exists
    yet (fresh install, before the bootstrap cadastro).
    """
    if settings.telegram_acts_as_username:
        user = db.query(User).filter(User.username == settings.telegram_acts_as_username).first()
        if user:
            return user.id
        logger.warning(
            "TELEGRAM_ACTS_AS_USERNAME=%s não encontrado; usando o primeiro admin cadastrado.",
            settings.telegram_acts_as_username,
        )
    admin = db.query(User).filter(User.is_admin.is_(True)).order_by(User.id).first()
    return admin.id if admin else None


def _is_authorized(update: Update) -> bool:
    if not settings.telegram_chat_id:
        return True  # no whitelist configured (dev mode)
    return str(update.effective_chat.id) == str(settings.telegram_chat_id)


async def _guard(update: Update) -> bool:
    if not _is_authorized(update):
        await update.message.reply_text("Não autorizado.")
        return False
    return True


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    await update.message.reply_text(
        "OneB ativo.\n\n"
        "Comandos:\n"
        "/watchlist - lista os ativos monitorados\n"
        "/add SYMBOL - adiciona um ativo (ex: /add AAPL)\n"
        "/remove SYMBOL - remove um ativo\n"
        "/status - resumo rápido dos preços atuais\n"
        "/relatorio - gera e envia um relatório em PDF\n"
        "/matinal - gera e envia a análise matinal (índices, níveis, noticias e calendário do dia)\n"
        "/pergunta <texto> - pergunta ao assistente de IA sobre a watchlist\n"
        "/radar - bot de radar da watchlist\n"
        "/score SYMBOL - score explicavel com dados reais\n"
        "/explicar SYMBOL - fatos, eventos e hipoteses\n"
        "/revisao - revisao dos sinais e riscos\n"
        "/playbooks - lista playbooks prontos\n"
        "/prompt_decisao SYMBOL - checklist antes de agir\n"
        "/decisao SYMBOL | tese | gatilho | invalidacao | prazo | risco\n"
        f"\nSeu chat_id: {update.effective_chat.id}"
    )


async def cmd_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    db = SessionLocal()
    try:
        user_id = resolve_acting_user_id(db)
        if user_id is None:
            await update.message.reply_text("Nenhuma conta cadastrada ainda. Faça o cadastro no dashboard primeiro.")
            return
        items = db.query(WatchlistItem).filter(WatchlistItem.user_id == user_id, WatchlistItem.active.is_(True)).all()
        if not items:
            await update.message.reply_text("Watchlist vazia. Use /add SYMBOL para adicionar.")
            return
        lines = [f"• {i.symbol} {('- ' + i.label) if i.label else ''}" for i in items]
        await update.message.reply_text("Watchlist:\n" + "\n".join(lines))
    finally:
        db.close()


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if not context.args:
        await update.message.reply_text("Uso: /add SYMBOL (ex: /add AAPL)")
        return
    symbol = context.args[0].upper().strip()
    db = SessionLocal()
    try:
        user_id = resolve_acting_user_id(db)
        if user_id is None:
            await update.message.reply_text("Nenhuma conta cadastrada ainda. Faça o cadastro no dashboard primeiro.")
            return
        existing = db.query(WatchlistItem).filter(WatchlistItem.user_id == user_id, WatchlistItem.symbol == symbol).first()
        if existing:
            existing.active = True
            db.commit()
            await update.message.reply_text(f"{symbol} reativado na watchlist.")
            return
        db.add(WatchlistItem(user_id=user_id, symbol=symbol))
        db.commit()
        await update.message.reply_text(f"{symbol} adicionado à watchlist.")
    finally:
        db.close()


async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if not context.args:
        await update.message.reply_text("Uso: /remove SYMBOL")
        return
    symbol = context.args[0].upper().strip()
    db = SessionLocal()
    try:
        user_id = resolve_acting_user_id(db)
        if user_id is None:
            await update.message.reply_text("Nenhuma conta cadastrada ainda. Faça o cadastro no dashboard primeiro.")
            return
        item = db.query(WatchlistItem).filter(WatchlistItem.user_id == user_id, WatchlistItem.symbol == symbol).first()
        if not item:
            await update.message.reply_text(f"{symbol} não está na watchlist.")
            return
        item.active = False
        db.commit()
        await update.message.reply_text(f"{symbol} removido da watchlist.")
    finally:
        db.close()


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    from app.models import PriceSnapshot

    db = SessionLocal()
    try:
        user_id = resolve_acting_user_id(db)
        if user_id is None:
            await update.message.reply_text("Nenhuma conta cadastrada ainda. Faça o cadastro no dashboard primeiro.")
            return
        items = db.query(WatchlistItem).filter(WatchlistItem.user_id == user_id, WatchlistItem.active.is_(True)).all()
        if not items:
            await update.message.reply_text("Watchlist vazia.")
            return
        lines = []
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
            else:
                lines.append(f"{item.symbol}: sem dados ainda")
        await update.message.reply_text("Status:\n" + "\n".join(lines))
    finally:
        db.close()


async def cmd_relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    from app.reports import build_pdf_report

    await update.message.reply_text("Gerando relatório em PDF...")
    db = SessionLocal()
    try:
        user_id = resolve_acting_user_id(db)
        if user_id is None:
            await update.message.reply_text("Nenhuma conta cadastrada ainda. Faça o cadastro no dashboard primeiro.")
            return
        pdf_bytes = build_pdf_report(db, user_id)
    finally:
        db.close()

    filename = f"oneb-market-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}.pdf"
    await update.message.reply_document(document=InputFile(io.BytesIO(pdf_bytes), filename=filename))


async def cmd_matinal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    from app import morning_report

    await update.message.reply_chat_action("typing")
    db = SessionLocal()
    try:
        user_id = resolve_acting_user_id(db)
        if user_id is None:
            await update.message.reply_text("Nenhuma conta cadastrada ainda. Faça o cadastro no dashboard primeiro.")
            return
        report = await morning_report.generate_and_store(db, user_id)
    finally:
        db.close()
    await update.message.reply_text(f"☀️ {report.narrative}")


async def cmd_pergunta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if not context.args:
        await update.message.reply_text("Uso: /pergunta sua pergunta aqui (ex: /pergunta por que a AAPL caiu hoje?)")
        return

    from app.llm_client import answer_question
    from app.routers.assistant import build_assistant_context

    question = " ".join(context.args)
    await update.message.reply_chat_action("typing")

    db = SessionLocal()
    try:
        user_id = resolve_acting_user_id(db)
        if user_id is None:
            await update.message.reply_text("Nenhuma conta cadastrada ainda. Faça o cadastro no dashboard primeiro.")
            return
        ctx = build_assistant_context(db, user_id)
    finally:
        db.close()

    answer = await answer_question(question, ctx)
    await update.message.reply_text(answer)


async def cmd_radar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    from app.bots import radar_bot

    db = SessionLocal()
    try:
        await update.message.reply_text(radar_bot(db).body)
    finally:
        db.close()


async def cmd_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if not context.args:
        await update.message.reply_text("Uso: /score SYMBOL")
        return
    from app.bots import score_bot

    await update.message.reply_text("Buscando dados reais e calculando score...")
    db = SessionLocal()
    try:
        await update.message.reply_text(score_bot(db, context.args[0], refresh_real_data=True).body)
    finally:
        db.close()


async def cmd_explicar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if not context.args:
        await update.message.reply_text("Uso: /explicar SYMBOL")
        return
    from app.bots import explanation_bot

    await update.message.reply_text("Buscando dados reais e montando explicacao verificavel...")
    db = SessionLocal()
    try:
        await update.message.reply_text(explanation_bot(db, context.args[0], refresh_real_data=True).body)
    finally:
        db.close()


async def cmd_revisao(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    from app.bots import review_bot

    db = SessionLocal()
    try:
        await update.message.reply_text(review_bot(db).body)
    finally:
        db.close()


async def cmd_playbooks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    from app.intelligence import DEFAULT_PLAYBOOKS

    lines = ["Playbooks prontos:"]
    for playbook in DEFAULT_PLAYBOOKS:
        lines.append(f"- {playbook['name']}: {playbook['description']}")
    await update.message.reply_text("\n".join(lines))


async def cmd_prompt_decisao(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if not context.args:
        await update.message.reply_text("Uso: /prompt_decisao SYMBOL")
        return
    from app.bots import decision_prompt_bot

    await update.message.reply_text(decision_prompt_bot(context.args[0]).body)


async def cmd_decisao(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    raw = " ".join(context.args)
    parts = [part.strip() for part in raw.split("|")]
    if len(parts) < 2:
        await update.message.reply_text("Uso: /decisao SYMBOL | tese | gatilho | invalidacao | prazo | risco")
        return

    db = SessionLocal()
    try:
        decision = DecisionJournal(
            user_id=None,
            symbol=parts[0].upper(),
            thesis=parts[1],
            trigger=parts[2] if len(parts) > 2 else "",
            invalidation=parts[3] if len(parts) > 3 else "",
            timeframe=parts[4] if len(parts) > 4 else "",
            risk_notes=parts[5] if len(parts) > 5 else "",
        )
        db.add(decision)
        db.commit()
        await update.message.reply_text(f"Decisao registrada para {decision.symbol}.")
    finally:
        db.close()


def build_application() -> Application | None:
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN não configurado — bot do Telegram desativado.")
        return None

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_start))
    application.add_handler(CommandHandler("watchlist", cmd_watchlist))
    application.add_handler(CommandHandler("add", cmd_add))
    application.add_handler(CommandHandler("remove", cmd_remove))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("relatorio", cmd_relatorio))
    application.add_handler(CommandHandler("matinal", cmd_matinal))
    application.add_handler(CommandHandler("pergunta", cmd_pergunta))
    application.add_handler(CommandHandler("radar", cmd_radar))
    application.add_handler(CommandHandler("score", cmd_score))
    application.add_handler(CommandHandler("explicar", cmd_explicar))
    application.add_handler(CommandHandler("revisao", cmd_revisao))
    application.add_handler(CommandHandler("playbooks", cmd_playbooks))
    application.add_handler(CommandHandler("prompt_decisao", cmd_prompt_decisao))
    application.add_handler(CommandHandler("decisao", cmd_decisao))
    return application


async def send_alert(application: Application | None, message: str) -> bool:
    if application is None or not settings.telegram_chat_id:
        return False
    try:
        await application.bot.send_message(chat_id=settings.telegram_chat_id, text=message)
        return True
    except Exception:
        logger.exception("Falha ao enviar alerta via Telegram")
        return False
