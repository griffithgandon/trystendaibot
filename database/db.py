import sqlite3
import time
import threading
from config import DB_PATH


# ===== CONNECT =====
conn = sqlite3.connect(
    DB_PATH,
    check_same_thread=False
)

# Один глобальный Lock для всех операций с БД
# Защищает от гонок при многопоточном polling
_lock = threading.Lock()

cursor = conn.cursor()


# ===== USERS TABLE =====
with _lock:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        telegram_username TEXT,
        sub_until INTEGER DEFAULT 0,
        reminded INTEGER DEFAULT 0
    )
    """)
    conn.commit()

# ===== MIGRATIONS =====
try:
    cursor.execute("ALTER TABLE users ADD COLUMN reminded INTEGER DEFAULT 0")
    conn.commit()
    print("MIGRATION: added column 'reminded'")
except Exception:
    pass  # Колонка уже существует — всё ок

# ===== PENDING PAYMENTS TABLE =====
with _lock:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pending_payments (
        user_id INTEGER PRIMARY KEY,
        tariff_id TEXT,
        created_at INTEGER
    )
    """)
    conn.commit()


# ── Хелпер ───────────────────────────────────────────────────────────────────

def _execute(query: str, params: tuple = ()):
    """Thread-safe execute + commit."""
    with _lock:
        cursor.execute(query, params)
        conn.commit()
        return cursor


def _fetchone(query: str, params: tuple = ()):
    with _lock:
        cursor.execute(query, params)
        return cursor.fetchone()


def _fetchall(query: str, params: tuple = ()):
    with _lock:
        cursor.execute(query, params)
        return cursor.fetchall()


# ===== USERS =====
def add_user(user_id: int, telegram_username: str | None = None):
    with _lock:
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, telegram_username) VALUES (?, ?)",
            (user_id, telegram_username)
        )
        if telegram_username:
            cursor.execute(
                "UPDATE users SET telegram_username=? WHERE user_id=?",
                (telegram_username, user_id)
            )
        conn.commit()


def save_username(user_id: int, username: str):
    _execute(
        "UPDATE users SET username=? WHERE user_id=?",
        (username, user_id)
    )


def get_username(user_id: int) -> str | None:
    row = _fetchone("SELECT username FROM users WHERE user_id=?", (user_id,))
    return row[0] if row else None


def get_telegram_username(user_id: int) -> str | None:
    row = _fetchone("SELECT telegram_username FROM users WHERE user_id=?", (user_id,))
    return row[0] if row else None


# ===== SUBSCRIPTIONS =====
def set_subscription(user_id: int, days: int):
    now = int(time.time())

    row = _fetchone("SELECT sub_until FROM users WHERE user_id=?", (user_id,))
    current_sub = row[0] if row else 0

    expire = (current_sub + days * 86400) if current_sub > now else (now + days * 86400)

    _execute(
        "UPDATE users SET sub_until=?, reminded=0 WHERE user_id=?",
        (expire, user_id)
    )


def has_sub(user_id: int) -> bool:
    row = _fetchone("SELECT sub_until FROM users WHERE user_id=?", (user_id,))
    return bool(row and row[0] > int(time.time()))


def remove_sub(user_id: int):
    _execute("UPDATE users SET sub_until=0 WHERE user_id=?", (user_id,))


def get_sub_until(user_id: int) -> int:
    row = _fetchone("SELECT sub_until FROM users WHERE user_id=?", (user_id,))
    return row[0] if row else 0


# ===== PENDING PAYMENTS =====
def add_pending_payment(user_id: int, tariff_id: str):
    _execute(
        "INSERT OR REPLACE INTO pending_payments (user_id, tariff_id, created_at) VALUES (?, ?, ?)",
        (user_id, tariff_id, int(time.time()))
    )


def clear_old_pending():
    _execute(
        "DELETE FROM pending_payments WHERE created_at < ?",
        (int(time.time()) - 1800,)
    )


def has_pending_payment(user_id: int) -> bool:
    clear_old_pending()
    row = _fetchone("SELECT 1 FROM pending_payments WHERE user_id=?", (user_id,))
    return row is not None


def remove_pending_payment(user_id: int):
    _execute("DELETE FROM pending_payments WHERE user_id=?", (user_id,))


def get_pending_payments() -> list:
    return _fetchall(
        "SELECT user_id, tariff_id, created_at FROM pending_payments ORDER BY created_at DESC"
    )


# ===== STATS =====
def get_total_users() -> int:
    row = _fetchone("SELECT COUNT(*) FROM users")
    return row[0] if row else 0


def get_total_subs() -> int:
    row = _fetchone(
        "SELECT COUNT(*) FROM users WHERE sub_until > ?",
        (int(time.time()),)
    )
    return row[0] if row else 0


# ===== REMINDER FLAG =====
def get_users_expiring_soon() -> list:
    """
    Возвращает пользователей, у которых подписка истекает в течение 48 часов
    и которым ещё НЕ отправляли напоминание (reminded=0).
    """
    now = int(time.time())
    two_days = now + 2 * 86400
    return _fetchall(
        "SELECT user_id, sub_until FROM users WHERE sub_until > ? AND sub_until < ? AND reminded=0",
        (now, two_days)
    )


def mark_reminded(user_id: int):
    _execute("UPDATE users SET reminded=1 WHERE user_id=?", (user_id,))


def get_expired_users() -> list:
    """Пользователи с истёкшей, но ещё не обнулённой подпиской."""
    return _fetchall(
        "SELECT user_id FROM users WHERE sub_until > 0 AND sub_until < ?",
        (int(time.time()),)
    )


# ===== USER LIST FOR ADMIN =====
def get_recent_users(limit: int = 20) -> list:
    return _fetchall(
        "SELECT user_id FROM users ORDER BY user_id DESC LIMIT ?",
        (limit,)
    )


# ===== ALL USER IDS (для рассылки) =====
def get_all_user_ids() -> list:
    return _fetchall("SELECT user_id FROM users")