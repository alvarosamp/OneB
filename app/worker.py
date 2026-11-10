from __future__ import annotations

import asyncio
import logging
import signal

from app.db import init_db
from app.scheduler import build_scheduler
from app.telegram_bot import build_application

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    init_db()
    stop_event = asyncio.Event()

    telegram_app = build_application()
    if telegram_app is not None:
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling()
        logger.info("Bot do Telegram iniciado no worker.")
    else:
        logger.warning("Worker rodando sem bot do Telegram.")

    scheduler = build_scheduler(telegram_app)
    scheduler.start()
    logger.info("Scheduler iniciado no worker.")

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    try:
        await stop_event.wait()
    finally:
        scheduler.shutdown(wait=False)
        if telegram_app is not None:
            await telegram_app.updater.stop()
            await telegram_app.stop()
            await telegram_app.shutdown()
        logger.info("Worker encerrado.")


if __name__ == "__main__":
    asyncio.run(main())
