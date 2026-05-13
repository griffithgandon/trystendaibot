import time
from database.db import cursor, conn
from config import ADMIN_ID


def check_subscriptions(bot):

    now = int(time.time())

    # ===== скоро закончится =====
    two_days = now + (2 * 86400)

    cursor.execute(
        """
        SELECT user_id, sub_until
        FROM users
        WHERE sub_until > ?
        AND sub_until < ?
        """,
        (
            now,
            two_days
        )
    )

    rows = cursor.fetchall()

    for user_id, sub_until in rows:

        try:

            hours_left = int(
                (sub_until - now) / 3600
            )

            # защита от спама
            if hours_left > 49:
                continue

            bot.send_message(
                user_id,
                f"""
⭐ Автопродление

⏰ Подписка закончится через 2 дня

💎 Продли VPN заранее,
чтобы не потерять доступ
"""
            )

        except Exception as e:
            print("REMINDER ERROR:", e)

    # ===== подписка закончилась =====
    cursor.execute(
        """
        SELECT user_id
        FROM users
        WHERE sub_until > 0
        AND sub_until < ?
        """,
        (now,)
    )

    expired = cursor.fetchall()

    for row in expired:

        user_id = row[0]

        try:

            bot.send_message(
                user_id,
                """
❌ Подписка закончилась

💎 Чтобы снова получить доступ —
продли VPN
"""
            )

            # чтобы не слал повторно
            cursor.execute(
                """
                UPDATE users
                SET sub_until = 0
                WHERE user_id = ?
                """,
                (user_id,)
            )

            conn.commit()

        except Exception as e:
            print("EXPIRED ERROR:", e)