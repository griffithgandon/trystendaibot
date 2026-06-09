import time

import aiosqlite

from bot.database.db import get_db

# ===== Users =====

async def add_user(user_id: int, telegram_username: str | None = None) -> None:
    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO users (user_id, telegram_username) VALUES (?, ?)",
        (user_id, telegram_username),
    )
    if telegram_username:
        await db.execute(
            "UPDATE users SET telegram_username = ? WHERE user_id = ?",
            (telegram_username, user_id),
        )
    await db.commit()


async def save_username(user_id: int, username: str) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE users SET username = ? WHERE user_id = ?",
        (username, user_id),
    )
    await db.commit()


async def get_username(user_id: int) -> str | None:
    db = await get_db()
    async with db.execute(
        "SELECT username FROM users WHERE user_id = ?", (user_id,)
    ) as cursor:
        row = await cursor.fetchone()
        return row["username"] if row else None


async def get_telegram_username(user_id: int) -> str | None:
    db = await get_db()
    async with db.execute(
        "SELECT telegram_username FROM users WHERE user_id = ?", (user_id,)
    ) as cursor:
        row = await cursor.fetchone()
        return row["telegram_username"] if row else None


# ===== Subscriptions =====

async def set_subscription(user_id: int, days: int) -> None:
    db = await get_db()
    now = int(time.time())

    async with db.execute(
        "SELECT sub_until FROM users WHERE user_id = ?", (user_id,)
    ) as cursor:
        row = await cursor.fetchone()
        current = row["sub_until"] if row else 0

    # Если подписка ещё активна — продлеваем от её конца,
    # иначе — от текущего момента
    expire = (current + days * 86400) if current > now else (now + days * 86400)

    await db.execute(
        "UPDATE users SET sub_until = ?, reminded = 0 WHERE user_id = ?",
        (expire, user_id),
    )
    await db.commit()


async def get_sub_until(user_id: int) -> int:
    db = await get_db()
    async with db.execute(
        "SELECT sub_until FROM users WHERE user_id = ?", (user_id,)
    ) as cursor:
        row = await cursor.fetchone()
        return row["sub_until"] if row else 0


async def has_sub(user_id: int) -> bool:
    return await get_sub_until(user_id) > int(time.time())


async def remove_sub(user_id: int) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE users SET sub_until = 0, sub_disabled = 0 WHERE user_id = ?",
        (user_id,),
    )
    await db.commit()


async def is_sub_disabled(user_id: int) -> bool:
    db = await get_db()
    async with db.execute(
        "SELECT sub_disabled FROM users WHERE user_id = ?", (user_id,)
    ) as cursor:
        row = await cursor.fetchone()
        return bool(row and row["sub_disabled"])


async def set_sub_disabled(user_id: int, disabled: bool) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE users SET sub_disabled = ? WHERE user_id = ?",
        (1 if disabled else 0, user_id),
    )
    await db.commit()


# ===== Trial =====

async def has_used_trial(user_id: int) -> bool:
    db = await get_db()
    async with db.execute(
        "SELECT trial_used FROM users WHERE user_id = ?", (user_id,)
    ) as cursor:
        row = await cursor.fetchone()
        return bool(row and row["trial_used"])


async def set_trial_used(user_id: int) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE users SET trial_used = 1 WHERE user_id = ?", (user_id,)
    )
    await db.commit()


# ===== Pending payments =====

async def _clear_old_pending(db: aiosqlite.Connection) -> None:
    """Удаляет обычные заявки старше 30 минут. Триальные не трогает."""
    await db.execute(
        "DELETE FROM pending_payments WHERE created_at < ? AND payment_type != 'trial'",
        (int(time.time()) - 1800,),
    )
    await db.commit()


async def add_pending_payment(
    user_id: int,
    tariff_id: str,
    payment_type: str = "new",
) -> None:
    db = await get_db()
    await db.execute(
        """
        INSERT OR REPLACE INTO pending_payments
            (user_id, tariff_id, created_at, payment_type)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, tariff_id, int(time.time()), payment_type),
    )
    await db.commit()


async def has_pending_payment(user_id: int) -> bool:
    db = await get_db()
    await _clear_old_pending(db)
    async with db.execute(
        "SELECT 1 FROM pending_payments WHERE user_id = ?", (user_id,)
    ) as cursor:
        return await cursor.fetchone() is not None


async def get_pending_payment_info(user_id: int) -> dict | None:
    db = await get_db()
    async with db.execute(
        "SELECT tariff_id, payment_type FROM pending_payments WHERE user_id = ?",
        (user_id,),
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        return {"tariff_id": row["tariff_id"], "payment_type": row["payment_type"]}


async def remove_pending_payment(user_id: int) -> None:
    db = await get_db()
    await db.execute(
        "DELETE FROM pending_payments WHERE user_id = ?", (user_id,)
    )
    await db.commit()


async def get_pending_payments() -> list[aiosqlite.Row]:
    db = await get_db()
    async with db.execute(
        """
        SELECT user_id, tariff_id, created_at, payment_type
        FROM pending_payments
        WHERE payment_type != 'trial'
        ORDER BY created_at DESC
        """
    ) as cursor:
        return list(await cursor.fetchall())


async def get_pending_trials() -> list[aiosqlite.Row]:
    db = await get_db()
    async with db.execute(
        """
        SELECT user_id, tariff_id, created_at
        FROM pending_payments
        WHERE payment_type = 'trial'
        ORDER BY created_at DESC
        """
    ) as cursor:
        return list(await cursor.fetchall())


# ===== Reminders =====

async def get_users_expiring_soon() -> list[aiosqlite.Row]:
    """Подписки истекают в течение 48 часов, напоминание ещё не отправлялось."""
    db = await get_db()
    now = int(time.time())
    async with db.execute(
        """
        SELECT user_id, sub_until FROM users
        WHERE sub_until > ? AND sub_until < ? AND reminded = 0
        """,
        (now, now + 2 * 86400),
    ) as cursor:
        return list(await cursor.fetchall())


async def mark_reminded(user_id: int) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE users SET reminded = 1 WHERE user_id = ?", (user_id,)
    )
    await db.commit()


async def get_expired_users() -> list[aiosqlite.Row]:
    """Подписка истекла, но ещё не обнулена (sub_until > 0)."""
    db = await get_db()
    async with db.execute(
        "SELECT user_id FROM users WHERE sub_until > 0 AND sub_until < ?",
        (int(time.time()),),
    ) as cursor:
        return list(await cursor.fetchall())


# ===== Stats =====

async def get_total_users() -> int:
    db = await get_db()
    async with db.execute("SELECT COUNT(*) FROM users") as cursor:
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_total_subs() -> int:
    db = await get_db()
    async with db.execute(
        "SELECT COUNT(*) FROM users WHERE sub_until > ?", (int(time.time()),)
    ) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_total_trials() -> int:
    db = await get_db()
    async with db.execute(
        "SELECT COUNT(*) FROM users WHERE trial_used = 1"
    ) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_recent_users(limit: int = 20) -> list[aiosqlite.Row]:
    db = await get_db()
    async with db.execute(
        "SELECT user_id FROM users ORDER BY user_id DESC LIMIT ?", (limit,)
    ) as cursor:
        return list(await cursor.fetchall())


async def get_all_user_ids() -> list[int]:
    db = await get_db()
    async with db.execute("SELECT user_id FROM users") as cursor:
        rows = await cursor.fetchall()
        return [row["user_id"] for row in rows]