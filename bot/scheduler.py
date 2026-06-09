"""
Планировщик фоновых задач (APScheduler).

Заменяет старый sub_loop на threading: проверка подписок раз в час.
"""

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.services.sub_checker import check_subscriptions

logger = logging.getLogger(__name__)

# Интервал проверки подписок (в старом боте sub_loop спал 3600 сек)
CHECK_INTERVAL_SECONDS = 3600


def create_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Создаёт и настраивает планировщик. Запуск — scheduler.start() в main."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_subscriptions,
        trigger="interval",
        seconds=CHECK_INTERVAL_SECONDS,
        args=[bot],
        id="check_subscriptions",
        replace_existing=True,
        max_instances=1,  # не запускать новый прогон, если прошлый ещё идёт
    )
    logger.info(
        "Планировщик настроен: проверка подписок раз в %s сек",
        CHECK_INTERVAL_SECONDS,
    )
    return scheduler
