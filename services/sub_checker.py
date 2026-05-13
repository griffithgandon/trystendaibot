import time
from database.db import (
    get_users_expiring_soon,
    mark_reminded,
    get_expired_users,
    remove_sub,
    conn,
    cursor,
)


def check_subscriptions(bot):
    # ===== Скоро закончится (один раз за цикл) =====
    for user_id, sub_until in get_users_expiring_soon():
        try:
            hours_left = int((sub_until - time.time()) / 3600)

            bot.send_message(
                user_id,
                f"⭐ Подписка закончится через ~{hours_left} ч.\n\n"
                "💎 Продли VPN заранее, чтобы не потерять доступ."
            )

            # Помечаем — больше не напоминаем до следующей подписки
            mark_reminded(user_id)

        except Exception as e:
            print("REMINDER ERROR:", e)

    # ===== Подписка истекла =====
    for (user_id,) in get_expired_users():
        try:
            bot.send_message(
                user_id,
                "❌ Подписка закончилась.\n\n"
                "💎 Чтобы снова получить доступ — продли VPN."
            )
        except Exception as e:
            print("EXPIRED NOTIFY ERROR:", e)

        # Обнуляем независимо от успеха отправки
        try:
            remove_sub(user_id)
        except Exception as e:
            print("EXPIRED RESET ERROR:", e)