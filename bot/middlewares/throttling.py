"""
Rate limiting для aiogram.

Содержит:
  - RateLimiter: in-memory token-bucket (asyncio однопоточный, блокировки не нужны)
  - ThrottlingMiddleware: глобальный лимит на все апдейты
  - именованные лимитеры + check_rate_limit() для точечных лимитов в хендлерах
"""

import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User


class RateLimiter:
    """Token-bucket: не более max_calls вызовов за period секунд на user_id."""

    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self._calls: dict[int, list[float]] = defaultdict(list)

    def is_allowed(self, user_id: int) -> bool:
        now = time.time()
        cutoff = now - self.period

        calls = [t for t in self._calls[user_id] if t > cutoff]
        if len(calls) >= self.max_calls:
            self._calls[user_id] = calls
            return False

        calls.append(now)
        self._calls[user_id] = calls
        return True

    def cleanup(self) -> None:
        """Периодическая очистка памяти от неактивных юзеров."""
        cutoff = time.time() - self.period
        for uid in list(self._calls.keys()):
            self._calls[uid] = [t for t in self._calls[uid] if t > cutoff]
            if not self._calls[uid]:
                del self._calls[uid]


# ── Глобальные лимитеры (перенос значений из старого rate_limiter.py) ──

global_limiter = RateLimiter(max_calls=20, period=10)     # любые действия
payment_limiter = RateLimiter(max_calls=3, period=600)    # платёжные заявки
support_limiter = RateLimiter(max_calls=5, period=3600)   # сообщения в поддержку
start_limiter = RateLimiter(max_calls=5, period=60)       # /start


_THROTTLE_MSG = "⏳ Слишком много запросов. Подождите немного."


class ThrottlingMiddleware(BaseMiddleware):
    """Глобальный анти-флуд. Вешается на message и callback_query."""

    def __init__(self, limiter: RateLimiter | None = None):
        self.limiter = limiter or global_limiter

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")

        if user and not self.limiter.is_allowed(user.id):
            # CallbackQuery — отвечаем алертом, Message — молча игнорируем
            if isinstance(event, CallbackQuery):
                await event.answer(_THROTTLE_MSG, show_alert=True)
            return None  # апдейт дальше не идёт

        return await handler(event, data)


async def check_rate_limit(
    event: Message | CallbackQuery,
    limiter: RateLimiter,
) -> bool:
    """
    Точечный лимит внутри хендлера (payment/support/start).

        if not await check_rate_limit(call, payment_limiter):
            return
    """
    user = event.from_user
    if user is None or limiter.is_allowed(user.id):
        return True

    if isinstance(event, CallbackQuery):
        await event.answer(_THROTTLE_MSG, show_alert=True)
    else:
        await event.answer(_THROTTLE_MSG)
    return False
