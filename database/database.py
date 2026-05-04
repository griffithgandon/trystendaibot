import sqlite3
import time
from config import DB_PATH

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    sub_until INTEGER DEFAULT 0,
    username TEXT
)
""")
conn.commit()

# 🔥 фикс для старой базы
try:
    cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
    conn.commit()
except:
    pass


def add_user(user_id):
    cursor.execute(
        "INSERT OR IGNORE INTO users(user_id) VALUES(?)",
        (user_id,)
    )
    conn.commit()


def save_username(user_id, username):
    cursor.execute(
        "UPDATE users SET username=? WHERE user_id=?",
        (username, user_id)
    )
    conn.commit()


def get_username(user_id):
    cursor.execute(
        "SELECT username FROM users WHERE user_id=?",
        (user_id,)
    )
    row = cursor.fetchone()
    return row[0] if row and row[0] else None


def set_subscription(user_id, days):
    expire = int(time.time()) + days * 86400

    cursor.execute(
        "UPDATE users SET sub_until=? WHERE user_id=?",
        (expire, user_id)
    )
    conn.commit()


def get_subscription(user_id):
    cursor.execute(
        "SELECT sub_until FROM users WHERE user_id=?",
        (user_id,)
    )
    row = cursor.fetchone()
    return int(row[0]) if row and row[0] else 0


def has_sub(user_id):
    return get_subscription(user_id) > int(time.time())