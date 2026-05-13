import time
import threading
from collections import defaultdict


class RateLimiter:
    """
    Token bucket rate limiter.
    Потокобезопасен, не требует Redis.
    """

    def __init__(self, max_calls: int, period: float):
        """
        max_calls — максимум вызовов за period секунд
        period    — окно в секундах
        """
        self.max_calls = max_calls
        self.period = period
        self._lock = threading.Lock()
        # user_id -> список timestamp последних вызовов
        self._calls: dict[int, list[float]] = defaultdict(list)

    def is_allowed(self, user_id: int) -> bool:
        now = time.time()
        cutoff = now - self.period

        with self._lock:
            calls = self._calls[user_id]

            # Удаляем старые записи
            self._calls[user_id] = [t for t in calls if t > cutoff]

            if len(self._calls[user_id]) >= self.max_calls:
                return False

            self._calls[user_id].append(now)
            return True

    def cleanup(self):
        """Вызывать периодически (например, раз в час) для очистки памяти."""
        now = time.time()
        cutoff = now - self.period

        with self._lock:
            for uid in list(self._calls.keys()):
                self._calls[uid] = [t for t in self._calls[uid] if t > cutoff]
                if not self._calls[uid]:
                    del self._calls[uid]


# ── Глобальные лимитеры ───────────────────────────────────────────────────────

# Общий лимит: не более 20 любых действий за 10 секунд
global_limiter = RateLimiter(max_calls=20, period=10)

# Лимит для платёжных заявок: не более 3 за 10 минут
payment_limiter = RateLimiter(max_calls=3, period=600)

# Лимит для сообщений в поддержку: не более 5 за час
support_limiter = RateLimiter(max_calls=5, period=3600)

# Лимит для /start: не более 5 за минуту
start_limiter = RateLimiter(max_calls=5, period=60)


def rate_limit(bot, call_or_message, limiter: RateLimiter | None = None):
    """
    Декоратор-проверка. Возвращает True если запрос разрешён.
    При превышении отвечает пользователю и возвращает False.

    Использование:
        if not rate_limit(bot, call):
            return
    """
    if limiter is None:
        limiter = global_limiter

    # Работает и с Message, и с CallbackQuery
    user_id = (
        call_or_message.from_user.id
        if hasattr(call_or_message, "from_user")
        else call_or_message.chat.id
    )

    if limiter.is_allowed(user_id):
        return True

    # Тихо игнорируем либо отвечаем — зависит от типа объекта
    try:
        if hasattr(call_or_message, "id"):          # CallbackQuery
            bot.answer_callback_query(
                call_or_message.id,
                "⏳ Слишком много запросов. Подождите немного.",
                show_alert=True
            )
        else:                                        # Message
            bot.send_message(
                call_or_message.chat.id,
                "⏳ Слишком много запросов. Подождите немного."
            )
    except Exception:
        pass

    return False