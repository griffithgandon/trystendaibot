"""
Тесты bot/database/repo.py поверх in-memory БД (фикстура fresh_db).
Все функции репозитория асинхронные.
"""

import time

from bot.database import repo


class TestUsers:
    async def test_add_and_get_user(self, fresh_db):
        await repo.add_user(111, "john_doe")
        assert await repo.get_telegram_username(111) == "john_doe"

    async def test_add_user_twice_does_not_fail(self, fresh_db):
        await repo.add_user(222)
        await repo.add_user(222)

    async def test_save_and_get_username(self, fresh_db):
        await repo.add_user(333)
        await repo.save_username(333, "Иван")
        assert await repo.get_username(333) == "Иван"

    async def test_get_username_unknown(self, fresh_db):
        assert await repo.get_username(99999) is None

    async def test_telegram_username_updates_on_second_add(self, fresh_db):
        await repo.add_user(444, "old_name")
        await repo.add_user(444, "new_name")
        assert await repo.get_telegram_username(444) == "new_name"


class TestSubscriptions:
    async def test_no_sub_by_default(self, fresh_db):
        await repo.add_user(10)
        assert not await repo.has_sub(10)

    async def test_set_subscription_active(self, fresh_db):
        await repo.add_user(11)
        await repo.set_subscription(11, 30)
        assert await repo.has_sub(11)

    async def test_sub_until_in_future(self, fresh_db):
        await repo.add_user(12)
        await repo.set_subscription(12, 30)
        assert await repo.get_sub_until(12) > int(time.time())

    async def test_set_subscription_extends_existing(self, fresh_db):
        await repo.add_user(13)
        await repo.set_subscription(13, 30)
        first = await repo.get_sub_until(13)
        await repo.set_subscription(13, 30)
        assert await repo.get_sub_until(13) > first

    async def test_remove_sub_clears(self, fresh_db):
        await repo.add_user(14)
        await repo.set_subscription(14, 30)
        await repo.remove_sub(14)
        assert not await repo.has_sub(14)
        assert await repo.get_sub_until(14) == 0

    async def test_get_sub_until_unknown(self, fresh_db):
        assert await repo.get_sub_until(99998) == 0


class TestSubDisabled:
    async def test_not_disabled_by_default(self, fresh_db):
        await repo.add_user(20)
        assert not await repo.is_sub_disabled(20)

    async def test_set_disabled_true(self, fresh_db):
        await repo.add_user(21)
        await repo.set_sub_disabled(21, True)
        assert await repo.is_sub_disabled(21)

    async def test_set_disabled_false_clears(self, fresh_db):
        await repo.add_user(22)
        await repo.set_sub_disabled(22, True)
        await repo.set_sub_disabled(22, False)
        assert not await repo.is_sub_disabled(22)

    async def test_remove_sub_clears_disabled(self, fresh_db):
        await repo.add_user(23)
        await repo.set_subscription(23, 30)
        await repo.set_sub_disabled(23, True)
        await repo.remove_sub(23)
        assert not await repo.is_sub_disabled(23)


class TestTrial:
    async def test_trial_not_used_by_default(self, fresh_db):
        await repo.add_user(30)
        assert not await repo.has_used_trial(30)

    async def test_set_trial_used(self, fresh_db):
        await repo.add_user(31)
        await repo.set_trial_used(31)
        assert await repo.has_used_trial(31)

    async def test_total_trials_counts(self, fresh_db):
        for uid in (40, 41, 42):
            await repo.add_user(uid)
        await repo.set_trial_used(40)
        await repo.set_trial_used(41)
        assert await repo.get_total_trials() == 2


class TestPendingPayments:
    async def test_no_pending_by_default(self, fresh_db):
        await repo.add_user(50)
        assert not await repo.has_pending_payment(50)

    async def test_add_pending(self, fresh_db):
        await repo.add_user(51)
        await repo.add_pending_payment(51, "1")
        assert await repo.has_pending_payment(51)

    async def test_remove_pending(self, fresh_db):
        await repo.add_user(52)
        await repo.add_pending_payment(52, "2")
        await repo.remove_pending_payment(52)
        assert not await repo.has_pending_payment(52)

    async def test_pending_info(self, fresh_db):
        await repo.add_user(53)
        await repo.add_pending_payment(53, "3", payment_type="renew")
        info = await repo.get_pending_payment_info(53)
        assert info is not None
        assert info["tariff_id"] == "3"
        assert info["payment_type"] == "renew"

    async def test_pending_info_missing(self, fresh_db):
        assert await repo.get_pending_payment_info(99997) is None

    async def test_add_pending_replaces(self, fresh_db):
        await repo.add_user(54)
        await repo.add_pending_payment(54, "1", payment_type="new")
        await repo.add_pending_payment(54, "2", payment_type="renew")
        info = await repo.get_pending_payment_info(54)
        assert info is not None
        assert info["tariff_id"] == "2"

    async def test_pending_trials_filtered(self, fresh_db):
        await repo.add_user(60)
        await repo.add_user(61)
        await repo.add_pending_payment(60, "trial", payment_type="trial")
        await repo.add_pending_payment(61, "1", payment_type="new")
        trial_ids = [row["user_id"] for row in await repo.get_pending_trials()]
        assert 60 in trial_ids
        assert 61 not in trial_ids

    async def test_pending_payments_excludes_trials(self, fresh_db):
        await repo.add_user(62)
        await repo.add_user(63)
        await repo.add_pending_payment(62, "trial", payment_type="trial")
        await repo.add_pending_payment(63, "1", payment_type="new")
        ids = [row["user_id"] for row in await repo.get_pending_payments()]
        assert 63 in ids
        assert 62 not in ids


class TestReminders:
    async def test_expiring_soon_returns_user(self, fresh_db):
        await repo.add_user(70)
        await repo.set_subscription(70, 1)  # истекает через ~1 день (<48ч)
        ids = [r["user_id"] for r in await repo.get_users_expiring_soon()]
        assert 70 in ids

    async def test_mark_reminded_excludes(self, fresh_db):
        await repo.add_user(71)
        await repo.set_subscription(71, 1)
        await repo.mark_reminded(71)
        ids = [r["user_id"] for r in await repo.get_users_expiring_soon()]
        assert 71 not in ids

    async def test_expired_users_detected(self, fresh_db):
        await repo.add_user(72)
        db = await fresh_db.get_db()
        await db.execute(
            "UPDATE users SET sub_until=? WHERE user_id=?",
            (int(time.time()) - 3600, 72),
        )
        await db.commit()
        ids = [r["user_id"] for r in await repo.get_expired_users()]
        assert 72 in ids


class TestStats:
    async def test_total_users_counts(self, fresh_db):
        before = await repo.get_total_users()
        await repo.add_user(80)
        await repo.add_user(81)
        assert await repo.get_total_users() == before + 2

    async def test_total_subs_counts_active(self, fresh_db):
        await repo.add_user(82)
        before = await repo.get_total_subs()
        await repo.set_subscription(82, 30)
        assert await repo.get_total_subs() == before + 1

    async def test_all_user_ids(self, fresh_db):
        await repo.add_user(90)
        await repo.add_user(91)
        ids = await repo.get_all_user_ids()
        assert 90 in ids and 91 in ids
