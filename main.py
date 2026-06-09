"""
Точка входа бота (aiogram).

Заменяет старый telebot-вариант на infinity_polling + threading.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import get_settings
from bot.database.db import close_db, init_db
from bot.handlers import get_routers
from bot.middlewares.error_handler import setup_error_handler
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.scheduler import create_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()

    # parse_mode=None — тексты отправляются как plain (как в старом боте),
    # чтобы @ник и подчёркивания не ломали разметку.
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )
    # FSM в памяти. Для продакшена можно заменить на RedisStorage(settings.redis_url).
    dp = Dispatcher(storage=MemoryStorage())

    # Роутеры
    for router in get_routers():
        dp.include_router(router)

    # Анти-флуд на сообщения и колбэки
    throttling = ThrottlingMiddleware()
    dp.message.middleware(throttling)
    dp.callback_query.middleware(throttling)

    # Глобальный обработчик ошибок
    setup_error_handler(dp)

    # База данных
    await init_db()

    # Планировщик (проверка подписок раз в час)
    scheduler = create_scheduler(bot)
    scheduler.start()

    try:
        logger.info("BOT STARTED")
        await bot.delete_webhook(drop_pending_updates=True)  # как skip_pending=True
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("BOT STOPPED")
