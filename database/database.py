import sqlite3
import time

conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    vpn_id TEXT,
    sub_until INTEGER DEFAULT 0)
""")
conn.commit()


def add_user(user_id):
    cursor.execute(
        "INSERT OR IGNORE INTO users(user_id) VALUES(?)",
        (user_id,)
    )
    conn.commit()


def set_subscription(user_id, days):
    expire = int(time.time()) + days * 86400

    cursor.execute("""
    UPDATE users
    SET sub_until=?
    WHERE user_id=?
    """, (expire, user_id))

    conn.commit()


def get_subscription(user_id):
    cursor.execute(
        "SELECT sub_until FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cursor.fetchone()

    if not row or not row[0]:
        return 0

    return int(row[0])


def has_sub(user_id):
    sub = int(get_subscription(user_id))
    return sub > int(time.time())


def save_vpn_id(user_id, vpn_id):
    cursor.execute("""
    UPDATE users
    SET vpn_id=?
    WHERE user_id=?
    """, (vpn_id, user_id))

    conn.commit()


def get_vpn_id(user_id):
    cursor.execute(
        "SELECT vpn_id FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cursor.fetchone()

    if row:
        return row[0]
    return None