import time
from database.db import (
    get_users_expiring_soon,
    mark_reminded,
    get_expired_users,
    remove_sub,
)
from services.vpn import delete_user


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

        # 1. Удаляем конфиг с VPN-панели
        try:
            deleted = delete_user(user_id)
            print(f"VPN DELETE user={user_id} success={deleted}")
        except Exception as e:
            print(f"VPN DELETE ERROR user={user_id}:", e)

        # 2. Обнуляем подписку в БД
        try:
            remove_sub(user_id)
        except Exception as e:
            print(f"SUB RESET ERROR user={user_id}:", e)

        # 3. Уведомляем пользователя
        try:
            bot.send_message(
                user_id,
                "❌ Подписка закончилась — VPN отключён.\n\n"
                "💎 Чтобы снова получить доступ, продли VPN."
            )
        except Exception as e:
            print(f"EXPIRED NOTIFY ERROR user={user_id}:", e)