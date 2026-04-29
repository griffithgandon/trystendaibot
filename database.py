import sqlite3
from datetime import datetime, timedelta

db = sqlite3.connect("bot.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    sub_until TEXT,
    total_payments INTEGER DEFAULT 0
)
""")

db.commit()


def add_user(user_id):
    cursor.execute(
        "INSERT OR IGNORE INTO users(user_id) VALUES(?)",
        (user_id,)
    )
    db.commit()


def activate_sub(user_id, days):
    expire = datetime.now() + timedelta(days=days)

    cursor.execute("""
    UPDATE users
    SET sub_until=?,
        total_payments = total_payments + 1
    WHERE user_id=?
    """, (expire.isoformat(), user_id))

    db.commit()


def has_sub(user_id):
    cursor.execute(
        "SELECT sub_until FROM users WHERE user_id=?",
        (user_id,)
    )

    result = cursor.fetchone()

    if result and result[0]:
        return datetime.fromisoformat(result[0]) > datetime.now()

    return False


def get_stats():
    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(total_payments) FROM users")
    payments = cursor.fetchone()[0] or 0

    return users_count, payments


def get_users():
    cursor.execute("SELECT user_id FROM users")
    return cursor.fetchall()