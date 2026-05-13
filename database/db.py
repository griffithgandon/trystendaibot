import sqlite3
import time
from config import DB_PATH


# ===== CONNECT =====
conn = sqlite3.connect(
    DB_PATH,
    check_same_thread=False
)

cursor = conn.cursor()


# ===== USERS TABLE =====
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    telegram_username TEXT,
    sub_until INTEGER DEFAULT 0
)
""")

conn.commit()


# ===== PENDING PAYMENTS TABLE =====
cursor.execute("""
CREATE TABLE IF NOT EXISTS pending_payments (
    user_id INTEGER PRIMARY KEY,
    tariff_id TEXT,
    created_at INTEGER
)
""")

conn.commit()


# ===== USERS =====
def add_user(user_id, telegram_username=None):

    cursor.execute(
        """
        INSERT OR IGNORE INTO users
        (user_id, telegram_username)
        VALUES (?, ?)
        """,
        (
            user_id,
            telegram_username
        )
    )

    # обновляем username telegram
    if telegram_username:

        cursor.execute(
            """
            UPDATE users
            SET telegram_username=?
            WHERE user_id=?
            """,
            (
                telegram_username,
                user_id
            )
        )

    conn.commit()


def save_username(user_id, username):

    cursor.execute(
        """
        UPDATE users
        SET username=?
        WHERE user_id=?
        """,
        (
            username,
            user_id
        )
    )

    conn.commit()


def get_username(user_id):

    cursor.execute(
        """
        SELECT username
        FROM users
        WHERE user_id=?
        """,
        (user_id,)
    )

    row = cursor.fetchone()

    return row[0] if row else None


def get_telegram_username(user_id):

    cursor.execute(
        """
        SELECT telegram_username
        FROM users
        WHERE user_id=?
        """,
        (user_id,)
    )

    row = cursor.fetchone()

    return row[0] if row else None


# ===== SUBSCRIPTIONS =====
def set_subscription(user_id, days):

    now = int(time.time())

    cursor.execute(
        """
        SELECT sub_until
        FROM users
        WHERE user_id=?
        """,
        (user_id,)
    )

    row = cursor.fetchone()

    current_sub = row[0] if row else 0

    # продление подписки
    if current_sub > now:
        expire = current_sub + (days * 86400)
    else:
        expire = now + (days * 86400)

    cursor.execute(
        """
        UPDATE users
        SET sub_until=?
        WHERE user_id=?
        """,
        (
            expire,
            user_id
        )
    )

    conn.commit()


def has_sub(user_id):

    cursor.execute(
        """
        SELECT sub_until
        FROM users
        WHERE user_id=?
        """,
        (user_id,)
    )

    row = cursor.fetchone()

    if not row:
        return False

    return row[0] > int(time.time())


def remove_sub(user_id):

    cursor.execute(
        """
        UPDATE users
        SET sub_until = 0
        WHERE user_id = ?
        """,
        (user_id,)
    )

    conn.commit()


def get_sub_until(user_id):

    cursor.execute(
        """
        SELECT sub_until
        FROM users
        WHERE user_id=?
        """,
        (user_id,)
    )

    row = cursor.fetchone()

    return row[0] if row else 0


# ===== PENDING PAYMENTS =====
def add_pending_payment(user_id, tariff_id):

    cursor.execute(
        """
        INSERT OR REPLACE INTO pending_payments
        (user_id, tariff_id, created_at)
        VALUES (?, ?, ?)
        """,
        (
            user_id,
            tariff_id,
            int(time.time())
        )
    )

    conn.commit()


def clear_old_pending():

    old_time = int(time.time()) - 1800

    cursor.execute(
        """
        DELETE FROM pending_payments
        WHERE created_at < ?
        """,
        (old_time,)
    )

    conn.commit()


def has_pending_payment(user_id):

    clear_old_pending()

    cursor.execute(
        """
        SELECT 1
        FROM pending_payments
        WHERE user_id=?
        """,
        (user_id,)
    )

    return cursor.fetchone() is not None


def remove_pending_payment(user_id):

    cursor.execute(
        """
        DELETE FROM pending_payments
        WHERE user_id=?
        """,
        (user_id,)
    )

    conn.commit()


def get_pending_payments():

    cursor.execute(
        """
        SELECT user_id, tariff_id, created_at
        FROM pending_payments
        ORDER BY created_at DESC
        """
    )

    return cursor.fetchall()


# ===== STATS =====
def get_total_users():

    cursor.execute(
        "SELECT COUNT(*) FROM users"
    )

    return cursor.fetchone()[0]


def get_total_subs():

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM users
        WHERE sub_until > ?
        """,
        (int(time.time()),)
    )

    return cursor.fetchone()[0]