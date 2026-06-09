"""
Тесты bot/middlewares/throttling.py — RateLimiter и check_rate_limit.

(Старый thread-safety тест убран: aiogram однопоточный, блокировок больше нет.)
"""

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.middlewares.throttling import RateLimiter, check_rate_limit


class TestRateLimiter:
    def test_allows_within_limit(self):
        limiter = RateLimiter(max_calls=5, period=10)
        assert all(limiter.is_allowed(1) for _ in range(5))

    def test_blocks_over_limit(self):
        limiter = RateLimiter(max_calls=3, period=10)
        for _ in range(3):
            limiter.is_allowed(2)
        assert limiter.is_allowed(2) is False

    def test_different_users_independent(self):
        limiter = RateLimiter(max_calls=2, period=10)
        limiter.is_allowed(1)
        limiter.is_allowed(1)
        assert limiter.is_allowed(1) is False
        assert limiter.is_allowed(2) is True

    def test_exactly_at_limit(self):
        limiter = RateLimiter(max_calls=1, period=10)
        assert limiter.is_allowed(6) is True
        assert limiter.is_allowed(6) is False

    def test_window_expires(self):
        limiter = RateLimiter(max_calls=1, period=0.1)
        assert limiter.is_allowed(3) is True
        assert limiter.is_allowed(3) is False
        time.sleep(0.15)
        assert limiter.is_allowed(3) is True

    def test_cleanup_removes_stale_entries(self):
        limiter = RateLimiter(max_calls=5, period=0.05)
        limiter.is_allowed(4)
        time.sleep(0.1)
        limiter.cleanup()
        assert 4 not in limiter._calls


class TestCheckRateLimit:
    def _event(self, user_id):
        # SimpleNamespace не является CallbackQuery -> в check_rate_limit
        # отработает ветка Message (event.answer(text))
        return SimpleNamespace(
            from_user=SimpleNamespace(id=user_id), answer=AsyncMock()
        )

    async def test_allowed_returns_true(self):
        limiter = RateLimiter(max_calls=5, period=10)
        event = self._event(100)
        assert await check_rate_limit(event, limiter) is True
        event.answer.assert_not_awaited()

    async def test_blocked_returns_false_and_answers(self):
        limiter = RateLimiter(max_calls=1, period=10)
        event = self._event(101)
        await check_rate_limit(event, limiter)  # съедаем лимит
        assert await check_rate_limit(event, limiter) is False
        event.answer.assert_awaited_once()

    async def test_no_user_returns_true(self):
        limiter = RateLimiter(max_calls=1, period=10)
        event = SimpleNamespace(from_user=None, answer=AsyncMock())
        assert await check_rate_limit(event, limiter) is True
        event.answer.assert_not_awaited()
