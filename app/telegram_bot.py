"""Telegram bot: envia alertas e deixa cada usuário Pro gerenciar a própria watchlist.

Um chat só é aceito depois de vinculado a uma conta (`/vincular CODIGO`, com o código gerado no
app). Chats desconhecidos não leem nem alteram nada.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime, timezone

from telegram import InputFile, Update
from telegram.ext import Application, CommandHandler, ContextTypes

import re

from fastapi import HTTPException

from app import billing
from app.config import settings
from app.db import SessionLocal
from app.models import User, WatchlistItem
from app.scope import active_watchlist, latest_snapshot

_SYMBOL_RE = re.compile(r"^[A-Z0-9^=.\-]{1,16}$")

logger = logging.getLogger(__name__)


def _linked_user(db, update: Update) -> User | None:
    """Usuário dono deste chat (vinculado com /vincular) que ainda tenha acesso Pro."""
    chat_id = str(update.effective_chat.id)
    user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
    if user is None or billing.effective_plan(user) != "pro":
        return None
    return user


async def _with_user(update: Update):
    """Abre a sessão e resolve o usuário; responde e devolve (None, None) se o chat não for válido."""
    db = SessionLocal()
    user = _linked_user(db, update)
    if user is None:
        db.close()
        await update.message.reply_text(
            "Chat não vinculado (ou plano Pro inativo). No app, abra Perfil > Telegram, gere o código "
            "e envie aqui: /vincular CODIGO"
        )
        return None, None
    return db, user


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Monitor NASDAQ.\n\n"
        "Para receber alertas aqui, gere um código em Perfil > Telegram no app e envie:\n"
        "/vincular CODIGO\n\n"
        "Depois de vinculado:\n"
        "/watchlist - lista os ativos monitorados\n"
        "/add SYMBOL - adiciona um ativo (ex: /add AAPL)\n"
        "/remove SYMBOL - remove um ativo\n"
        "/status - resumo rápido dos preços atuais\n"
        "/relatorio - gera e envia um relatório em PDF\n"
        "/matinal - análise matinal (índices, níveis, notícias e calendário do dia)\n"
        "/pergunta <texto> - pergunta ao assistente de IA sobre a watchlist\n"
        "/desvincular - para de receber mensagens neste chat\n\n"
        "Ferramenta de apoio à decisão; não é recomendação de investimento."
    )


async def cmd_vincular(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /vincular CODIGO (gere o código em Perfil > Telegram)")
        return
    code = context.args[0].strip().upper()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_link_code == code).first()
        if user is None:
            await update.message.reply_text("Código inválido ou já usado. Gere outro no app.")
            return
        if billing.effective_plan(user) != "pro":
            await update.message.reply_text("O Telegram faz parte do plano Pro.")
            return
        # um chat pertence a um usuário só
        db.query(User).filter(User.telegram_chat_id == str(update.effective_chat.id)).update(
            {User.telegram_chat_id: None}
        )
        user.telegram_chat_id = str(update.effective_chat.id)
        user.telegram_link_code = None  # uso único
        db.commit()
        await update.message.reply_text(f"Vinculado à conta {user.username}. Use /start para ver os comandos.")
    finally:
        db.close()


async def cmd_desvincular(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        db.query(User).filter(User.telegram_chat_id == str(update.effective_chat.id)).update(
            {User.telegram_chat_id: None}
        )
        db.commit()
        await update.message.reply_text("Chat desvinculado.")
    finally:
        db.close()


async def cmd_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, user = await _with_user(update)
    if db is None:
        return
    try:
        items = active_watchlist(db, user.id)
        if not items:
            await update.message.reply_text("Watchlist vazia. Use /add SYMBOL para adicionar.")
            return
        lines = [f"• {i.symbol} {('- ' + i.label) if i.label else ''}" for i in items]
        await update.message.reply_text("Watchlist:\n" + "\n".join(lines))
    finally:
        db.close()


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /add SYMBOL (ex: /add AAPL)")
        return
    db, user = await _with_user(update)
    if db is None:
        return
    symbol = context.args[0].upper().strip()
    try:
        if not _SYMBOL_RE.match(symbol):
            await update.message.reply_text("Símbolo inválido.")
            return
        try:
            billing.check_symbol_quota(db, user, symbol)
        except HTTPException as exc:
            await update.message.reply_text(exc.detail)
            return
        existing = (
            db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id, WatchlistItem.symbol == symbol).first()
        )
        if existing:
            existing.active = True
            db.commit()
            await update.message.reply_text(f"{symbol} reativado na watchlist.")
            return
        db.add(WatchlistItem(user_id=user.id, symbol=symbol))
        db.commit()
        await update.message.reply_text(f"{symbol} adicionado à watchlist.")
    finally:
        db.close()


async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /remove SYMBOL")
        return
    db, user = await _with_user(update)
    if db is None:
        return
    symbol = context.args[0].upper().strip()
    try:
        item = (
            db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id, WatchlistItem.symbol == symbol).first()
        )
        if not item:
            await update.message.reply_text(f"{symbol} não está na watchlist.")
            return
        item.active = False
        db.commit()
        await update.message.reply_text(f"{symbol} removido da watchlist.")
    finally:
        db.close()


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, user = await _with_user(update)
    if db is None:
        return
    try:
        items = active_watchlist(db, user.id)
        if not items:
            await update.message.reply_text("Watchlist vazia.")
            return
        lines = []
        for item in items:
            snap = latest_snapshot(db, item.id)
            if snap:
                arrow = "🔺" if snap.change_pct >= 0 else "🔻"
                lines.append(f"{item.symbol}: {snap.price:.2f} {arrow} {snap.change_pct:+.2f}%")
            else:
                lines.append(f"{item.symbol}: sem dados ainda")
        await update.message.reply_text("Status:\n" + "\n".join(lines))
    finally:
        db.close()


async def cmd_relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, user = await _with_user(update)
    if db is None:
        return
    from app.reports import build_pdf_report

    await update.message.reply_text("Gerando relatório em PDF...")
    try:
        pdf_bytes = build_pdf_report(db, user.id)
    finally:
        db.close()

    filename = f"monitor-nasdaq-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}.pdf"
    await update.message.reply_document(document=InputFile(io.BytesIO(pdf_bytes), filename=filename))


async def cmd_matinal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, user = await _with_user(update)
    if db is None:
        return
    from app import morning_report
    from app.models import MorningReport

    await update.message.reply_chat_action("typing")
    try:
        # reaproveita o relatório do dia (gerado pelo agendador) em vez de gastar IA a cada comando
        report = db.query(MorningReport).order_by(MorningReport.generated_at.desc()).first()
        fresh = report is not None and (datetime.now(timezone.utc) - _aware(report.generated_at)).total_seconds() < 6 * 3600
        if not fresh:
            report = await morning_report.generate_and_store(db)
        text = f"☀️ {report.narrative}"
    finally:
        db.close()
    await update.message.reply_text(text)


async def cmd_pergunta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /pergunta sua pergunta aqui (ex: /pergunta por que a AAPL caiu hoje?)")
        return
    db, user = await _with_user(update)
    if db is None:
        return

    from app.llm_client import answer_question
    from app.routers.assistant import build_assistant_context

    try:
        billing.consume_llm_quota(user)
    except HTTPException as exc:
        db.close()
        await update.message.reply_text(exc.detail)
        return

    question = " ".join(context.args)
    await update.message.reply_chat_action("typing")
    try:
        ctx = build_assistant_context(db, user.id)
    finally:
        db.close()

    answer = await answer_question(question, ctx)
    await update.message.reply_text(answer)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def build_application() -> Application | None:
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN não configurado — bot do Telegram desativado.")
        return None

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_start))
    application.add_handler(CommandHandler("vincular", cmd_vincular))
    application.add_handler(CommandHandler("desvincular", cmd_desvincular))
    application.add_handler(CommandHandler("watchlist", cmd_watchlist))
    application.add_handler(CommandHandler("add", cmd_add))
    application.add_handler(CommandHandler("remove", cmd_remove))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("relatorio", cmd_relatorio))
    application.add_handler(CommandHandler("matinal", cmd_matinal))
    application.add_handler(CommandHandler("pergunta", cmd_pergunta))
    return application


async def send_alert(application: Application | None, message: str, chat_id: str | None = None) -> bool:
    """Envia ao chat do usuário. Sem `chat_id` (ou sem bot) não envia nada."""
    if application is None or not chat_id:
        return False
    try:
        await application.bot.send_message(chat_id=chat_id, text=message)
        return True
    except Exception:
        logger.exception("Falha ao enviar alerta via Telegram")
        return False
