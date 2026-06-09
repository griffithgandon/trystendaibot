"""
Проверка подписок: напоминания об истечении и отключение истёкших.
Запускается планировщиком (APScheduler) периодически.
"""

import logging
import time

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot.database.repo import (
    get_expired_users,
    get_users_expiring_soon,
    mark_reminded,
    remove_sub,
    set_sub_disabled,
)
from bot.services.vpn import disable_user

logger = logging.getLogger(__name__)


async def check_subscriptions(bot: Bot) -> None:
    # ===== Скоро закончится (один раз за цикл) =====
    for row in await get_users_expiring_soon():
        user_id = row["user_id"]
        sub_until = row["sub_until"]
        try:
            hours_left = int((sub_until - time.time()) / 3600)
            await bot.send_message(
                user_id,
                f"⭐ Подписка закончится через ~{hours_left} ч.\n\n"
                "💎 Продли VPN заранее, чтобы не потерять доступ.",
            )
            await mark_reminded(user_id)
        except TelegramAPIError as e:
            logger.warning("REMINDER SEND FAILED user=%s: %s", user_id, e)
        except Exception as e:
            logger.error("REMINDER ERROR user=%s: %s", user_id, e)

    # ===== Подписка истекла =====
    for row in await get_expired_users():
        user_id = row["user_id"]

        # 1. Отключаем клиента на панели (не удаляем)
        try:
            disabled = await disable_user(user_id)
            logger.info("VPN DISABLE user=%s success=%s", user_id, disabled)
        except Exception as e:
            logger.error("VPN DISABLE ERROR user=%s: %s", user_id, e)

        # 2. Обнуляем подписку и ставим флаг disabled в БД
        try:
            await remove_sub(user_id)
            await set_sub_disabled(user_id, True)
        except Exception as e:
            logger.error("SUB RESET ERROR user=%s: %s", user_id, e)

        # 3. Уведомляем пользователя
        try:
            await bot.send_message(
                user_id,
                "❌ Подписка закончилась — VPN отключён.\n\n"
                "💎 Чтобы снова получить доступ, продли VPN.",
            )
        except TelegramAPIError as e:
            logger.warning("EXPIRED NOTIFY FAILED user=%s: %s", user_id, e)
        except Exception as e:
            logger.error("EXPIRED NOTIFY ERROR user=%s: %s", user_id, e)
