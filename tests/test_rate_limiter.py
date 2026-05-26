"""
Тесты для utils/rate_limiter.py
"""

import time
import threading
import sys
import os
import types as builtin_types

import pytest

# Гарантируем, что корень проекта есть в sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.rate_limiter import RateLimiter, rate_limit, global_limiter


class TestRateLimiter:
    def test_allows_within_limit(self):
        limiter = RateLimiter(max_calls=5, period=10)
        for _ in range(5):
            assert limiter.is_allowed(user_id=1) is True

    def test_blocks_over_limit(self):
        limiter = RateLimiter(max_calls=3, period=10)
        for _ in range(3):
            limiter.is_allowed(user_id=2)
        assert limiter.is_allowed(user_id=2) is False

    def test_different_users_independent(self):
        limiter = RateLimiter(max_calls=2, period=10)
        limiter.is_allowed(1)
        limiter.is_allowed(1)
        assert limiter.is_allowed(1) is False
        assert limiter.is_allowed(2) is True

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

    def test_thread_safety(self):
        """Параллельные вызовы не должны приводить к race condition."""
        limiter = RateLimiter(max_calls=100, period=5)
        results = []

        def worker():
            results.append(limiter.is_allowed(user_id=5))

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sum(results) == 50

    def test_exactly_at_limit_allowed(self):
        limiter = RateLimiter(max_calls=1, period=10)
        assert limiter.is_allowed(6) is True
        assert limiter.is_allowed(6) is False

    def test_zero_period_edge(self):
        """period=0: все записи сразу протухают."""
        limiter = RateLimiter(max_calls=1, period=0)
        assert limiter.is_allowed(7) is True
        assert limiter.is_allowed(7) is True


class TestRateLimitHelper:
    """Тесты вспомогательной функции rate_limit()."""

    def _make_call(self, user_id: int):
        return builtin_types.SimpleNamespace(
            from_user=builtin_types.SimpleNamespace(id=user_id),
            id="cq_id",
        )

    def _make_message(self, user_id: int, chat_id: int = None):
        return builtin_types.SimpleNamespace(
            from_user=builtin_types.SimpleNamespace(id=user_id),
            chat=builtin_types.SimpleNamespace(id=chat_id or user_id),
        )

    def test_returns_true_within_limit(self):
        bot = builtin_types.SimpleNamespace(
            answer_callback_query=lambda *a, **kw: None,
        )
        limiter = RateLimiter(max_calls=5, period=10)
        call = self._make_call(100)
        assert rate_limit(bot, call, limiter) is True

    def test_returns_false_over_limit(self):
        answered = []
        bot = builtin_types.SimpleNamespace(
            answer_callback_query=lambda *a, **kw: answered.append(True),
        )
        limiter = RateLimiter(max_calls=1, period=10)
        call = self._make_call(101)
        rate_limit(bot, call, limiter)
        result = rate_limit(bot, call, limiter)
        assert result is False
        assert len(answered) == 1

    def test_message_type_sends_text(self):
        sent = []
        bot = builtin_types.SimpleNamespace(
            send_message=lambda chat_id, text: sent.append(text),
            answer_callback_query=lambda *a, **kw: None,
        )
        limiter = RateLimiter(max_calls=1, period=10)
        msg = self._make_message(102)
        rate_limit(bot, msg, limiter)
        rate_limit(bot, msg, limiter)
        assert len(sent) == 1

    def test_uses_global_limiter_by_default(self):
        bot = builtin_types.SimpleNamespace(
            answer_callback_query=lambda *a, **kw: None,
        )
        call = self._make_call(999)
        result = rate_limit(bot, call)
        assert isinstance(result, bool)