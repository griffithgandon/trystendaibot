"""
Глобальный обработчик ошибок.

В aiogram необработанные исключения из хендлеров всплывают в Dispatcher
и попадают сюда через dp.errors. Заменяет старый декоратор handler_errors.
"""

import logging

from aiogram import Dispatcher
from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)


async def on_error(event: ErrorEvent) -> bool:
    logger.exception(
        "Необработанная ошибка в апдейте: %s", event.exception, exc_info=event.exception
    )

    # Если ошибка пришла из callback — гасим "часики" на кнопке
    callback = event.update.callback_query
    if callback is not None:
        try:
            await callback.answer("❌ Ошибка", show_alert=False)
        except Exception:
            pass

    return True  # помечаем как обработанную, чтобы не падал polling


def setup_error_handler(dp: Dispatcher) -> None:
    """Регистрирует глобальный обработчик ошибок на диспетчере."""
    dp.errors.register(on_error)
