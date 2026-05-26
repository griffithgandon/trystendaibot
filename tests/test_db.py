"""
Тесты для database/db.py

Каждый тест получает свежую in-memory БД через importlib,
независимо от .env и реального bot.db.
"""

import importlib.util
import sys
import os
import time
import types as builtin_types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_DB_SOURCE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "db.py"
)


def _fresh_db():
    """Загружает database/db.py с чистой in-memory SQLite. Без побочных эффектов."""
    fake_config = builtin_types.ModuleType("config")
    fake_config.DB_PATH = ":memory:"
    sys.modules["config"] = fake_config

    spec = importlib.util.spec_from_file_location("_testdb_isolated", _DB_SOURCE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def db():
    mod = _fresh_db()
    yield mod
    try:
        mod.conn.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Пользователи
# ---------------------------------------------------------------------------


class TestUsers:
    def test_add_and_get_user(self, db):
        db.add_user(111, "john_doe")
        assert db.get_telegram_username(111) == "john_doe"

    def test_add_user_twice_does_not_fail(self, db):
        db.add_user(222)
        db.add_user(222)

    def test_save_and_get_username(self, db):
        db.add_user(333)
        db.save_username(333, "Иван")
        assert db.get_username(333) == "Иван"

    def test_get_username_unknown_user(self, db):
        assert db.get_username(99999) is None

    def test_telegram_username_updates_on_second_add(self, db):
        db.add_user(444, "old_name")
        db.add_user(444, "new_name")
        assert db.get_telegram_username(444) == "new_name"


# ---------------------------------------------------------------------------
# Подписки
# ---------------------------------------------------------------------------


class TestSubscriptions:
    def test_no_sub_by_default(self, db):
        db.add_user(10)
        assert not db.has_sub(10)

    def test_set_subscription_gives_active_sub(self, db):
        db.add_user(11)
        db.set_subscription(11, 30)
        assert db.has_sub(11)

    def test_sub_until_is_in_future(self, db):
        db.add_user(12)
        db.set_subscription(12, 30)
        assert db.get_sub_until(12) > int(time.time())

    def test_set_subscription_extends_existing(self, db):
        db.add_user(13)
        db.set_subscription(13, 30)
        first = db.get_sub_until(13)
        db.set_subscription(13, 30)
        assert db.get_sub_until(13) > first

    def test_remove_sub_clears_subscription(self, db):
        db.add_user(14)
        db.set_subscription(14, 30)
        db.remove_sub(14)
        assert not db.has_sub(14)
        assert db.get_sub_until(14) == 0

    def test_get_sub_until_unknown_user(self, db):
        assert db.get_sub_until(99998) == 0


# ---------------------------------------------------------------------------
# Флаг sub_disabled
# ---------------------------------------------------------------------------


class TestSubDisabled:
    def test_not_disabled_by_default(self, db):
        db.add_user(20)
        assert not db.is_sub_disabled(20)

    def test_set_disabled_true(self, db):
        db.add_user(21)
        db.set_sub_disabled(21, True)
        assert db.is_sub_disabled(21)

    def test_set_disabled_false_clears_flag(self, db):
        db.add_user(22)
        db.set_sub_disabled(22, True)
        db.set_sub_disabled(22, False)
        assert not db.is_sub_disabled(22)

    def test_remove_sub_also_clears_disabled(self, db):
        db.add_user(23)
        db.set_subscription(23, 30)
        db.set_sub_disabled(23, True)
        db.remove_sub(23)
        assert not db.is_sub_disabled(23)


# ---------------------------------------------------------------------------
# Пробный период
# ---------------------------------------------------------------------------


class TestTrial:
    def test_trial_not_used_by_default(self, db):
        db.add_user(30)
        assert not db.has_used_trial(30)

    def test_set_trial_used(self, db):
        db.add_user(31)
        db.set_trial_used(31)
        assert db.has_used_trial(31)

    def test_get_total_trials_counts_correctly(self, db):
        for uid in (40, 41, 42):
            db.add_user(uid)
        db.set_trial_used(40)
        db.set_trial_used(41)
        assert db.get_total_trials() == 2


# ---------------------------------------------------------------------------
# Pending payments
# ---------------------------------------------------------------------------


class TestPendingPayments:
    def test_no_pending_by_default(self, db):
        db.add_user(50)
        assert not db.has_pending_payment(50)

    def test_add_pending_payment(self, db):
        db.add_user(51)
        db.add_pending_payment(51, "1")
        assert db.has_pending_payment(51)

    def test_remove_pending_payment(self, db):
        db.add_user(52)
        db.add_pending_payment(52, "2")
        db.remove_pending_payment(52)
        assert not db.has_pending_payment(52)

    def test_get_pending_payment_info(self, db):
        db.add_user(53)
        db.add_pending_payment(53, "3", payment_type="renew")
        info = db.get_pending_payment_info(53)
        assert info is not None
        assert info["tariff_id"] == "3"
        assert info["payment_type"] == "renew"

    def test_get_pending_payment_info_missing(self, db):
        assert db.get_pending_payment_info(99997) is None

    def test_add_pending_replaces_existing(self, db):
        db.add_user(54)
        db.add_pending_payment(54, "1", payment_type="new")
        db.add_pending_payment(54, "2", payment_type="renew")
        info = db.get_pending_payment_info(54)
        assert info["tariff_id"] == "2"

    def test_get_pending_trials_filters_correctly(self, db):
        db.add_user(60)
        db.add_user(61)
        db.add_pending_payment(60, "trial", payment_type="trial")
        db.add_pending_payment(61, "1", payment_type="new")
        trial_ids = [row[0] for row in db.get_pending_trials()]
        assert 60 in trial_ids
        assert 61 not in trial_ids


# ---------------------------------------------------------------------------
# Напоминания
# ---------------------------------------------------------------------------


class TestReminder:
    def test_expiring_soon_returns_user(self, db):
        db.add_user(70)
        expire = int(time.time()) + 86400
        db._execute(
            "UPDATE users SET sub_until=?, reminded=0 WHERE user_id=?", (expire, 70)
        )
        assert 70 in [r[0] for r in db.get_users_expiring_soon()]

    def test_mark_reminded_excludes_from_expiring(self, db):
        db.add_user(71)
        expire = int(time.time()) + 86400
        db._execute(
            "UPDATE users SET sub_until=?, reminded=0 WHERE user_id=?", (expire, 71)
        )
        db.mark_reminded(71)
        assert 71 not in [r[0] for r in db.get_users_expiring_soon()]

    def test_expired_users_detected(self, db):
        db.add_user(72)
        expire = int(time.time()) - 3600
        db._execute("UPDATE users SET sub_until=? WHERE user_id=?", (expire, 72))
        assert 72 in [r[0] for r in db.get_expired_users()]


# ---------------------------------------------------------------------------
# Статистика
# ---------------------------------------------------------------------------


class TestStats:
    def test_total_users_counts_added(self, db):
        before = db.get_total_users()
        db.add_user(80)
        db.add_user(81)
        assert db.get_total_users() == before + 2

    def test_total_subs_counts_active(self, db):
        db.add_user(82)
        before = db.get_total_subs()
        db.set_subscription(82, 30)
        assert db.get_total_subs() == before + 1

    def test_total_subs_excludes_expired(self, db):
        db.add_user(83)
        db._execute(
            "UPDATE users SET sub_until=? WHERE user_id=?", (int(time.time()) - 1, 83)
        )
        assert db.has_sub(83) is False
