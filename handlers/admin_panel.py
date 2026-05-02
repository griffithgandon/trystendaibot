from telebot import types
from config import ADMIN_ID
from database.database import *
from services.vpn import delete_user, create_user
import time


def register_admin(bot):

    # Admin panel and inline buttons
    @bot.message_handler(commands=['admin'])
    def admin_panel(message):
        if message.from_user.id not in ADMIN_ID:
            return

        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"))
        markup.row(types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"))
        markup.row(types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"))

        bot.send_message(message.chat.id, "⚙️ ADMIN PANEL", reply_markup=markup)

    # List users command
    @bot.callback_query_handler(func=lambda c: c.data == "admin_users")
    def users(call):
        if call.from_user.id not in ADMIN_ID:
            return

        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()

        if not users:
            bot.send_message(call.message.chat.id, "Нет пользователей")
            return

        user_ids = [str(u[0]) for u in users]

        text = "👥 Пользователи:\n\n" + "\n".join(user_ids)

        if len(text) > 4000:
            for i in range(0, len(user_ids), 100):
                bot.send_message(call.message.chat.id, "\n".join(user_ids[i:i + 100]))
        else:
            bot.send_message(call.message.chat.id, text)

        msg = bot.send_message(call.message.chat.id, "\nОтправь ID пользователя")
        bot.register_next_step_handler(msg, user_manage)

    def user_manage(message):
        if message.from_user.id not in ADMIN_ID:
            return

        try:
            user_id = int(message.text)
        except:
            bot.send_message(message.chat.id, "❌ Неверный ID")
            return

        markup = types.InlineKeyboardMarkup()

        markup.row(
            types.InlineKeyboardButton("✅ Выдать 30 дней", callback_data=f"give_{user_id}"),
            types.InlineKeyboardButton("❌ Забрать", callback_data=f"remove_{user_id}")
        )

        markup.row(
            types.InlineKeyboardButton("♻️ Пересоздать", callback_data=f"recreate_{user_id}")
        )

        bot.send_message(
            message.chat.id,
            f"Управление пользователем {user_id}",
            reply_markup=markup
        )

    # Give 30 days command
    @bot.callback_query_handler(func=lambda c: c.data.startswith("give_"))
    def give(call):
        if call.from_user.id not in ADMIN_ID:
            return

        user_id = int(call.data.split("_")[1])
        days = 30

        set_subscription(user_id, days)
        create_user(user_id, days)

        bot.send_message(user_id, "✅ Вам выдана подписка")
        bot.answer_callback_query(call.id, "Выдано")

    # Remove sub from server command
    @bot.callback_query_handler(func=lambda c: c.data.startswith("remove_"))
    def remove(call):
        if call.from_user.id not in ADMIN_ID:
            return

        user_id = int(call.data.split("_")[1])

        print("Удаляем:", user_id)

        try:
            success = delete_user(user_id)
            print("Удаление из панели:", success)
        except Exception as e:
            print("Ошибка:", e)

        cursor.execute(
            "UPDATE users SET sub_until = 0 WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()

        bot.answer_callback_query(call.id, "Удалено")

        bot.send_message(call.message.chat.id, f"❌ Подписка у {user_id} удалена")

        try:
            bot.send_message(user_id, "❌ Ваша подписка отключена")
        except:
            pass

    # ===== RECREATE =====
    @bot.callback_query_handler(func=lambda c: c.data.startswith("recreate_"))
    def recreate(call):
        if call.from_user.id not in ADMIN_ID:
            return

        user_id = int(call.data.split("_")[1])
        days = 30

        print("Пересоздаём:", user_id)

        try:
            delete_user(user_id)
        except:
            pass

        set_subscription(user_id, days)
        create_user(user_id, days)

        bot.answer_callback_query(call.id, "Пересоздано")

        bot.send_message(user_id, "♻️ Ваш VPN пересоздан")

    # Stats command
    @bot.callback_query_handler(func=lambda c: c.data == "admin_stats")
    def stats(call):
        if call.from_user.id not in ADMIN_ID:
            return

        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE sub_until > ?",
            (int(time.time()),)
        )
        active = cursor.fetchone()[0]

        bot.send_message(
            call.message.chat.id,
            f"""📊 Статистика\n👥 Пользователей: {total}\n💎 Активных: {active}"""
        )

    # Broadcast command
    @bot.callback_query_handler(func=lambda c: c.data == "admin_broadcast")
    def broadcast(call):
        if call.from_user.id not in ADMIN_ID:
            return

        msg = bot.send_message(call.message.chat.id, "Введите текст рассылки")
        bot.register_next_step_handler(msg, send_broadcast)

    def send_broadcast(message):
        if message.from_user.id not in ADMIN_ID:
            return

        text = message.text

        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()

        sent = 0

        for user in users:
            try:
                bot.send_message(user[0], text)
                sent += 1
            except:
                pass

        bot.send_message(message.chat.id, f"✅ Отправлено: {sent}")