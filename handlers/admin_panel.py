from telebot import types
from config import ADMIN_ID
from database.database import *
import time

def register_admin(bot):

    # ADMIN PANEL
    @bot.message_handler(commands=['admin'])
    def admin_panel(message):
        print('Admin command executed')
        if message.from_user.id not in ADMIN_ID:
            print('Admin id not found')
            return

        markup = types.InlineKeyboardMarkup()

        markup.row(
            types.InlineKeyboardButton(
                "👥 Пользователи",
                callback_data="admin_users"
            )
        )

        markup.row(
            types.InlineKeyboardButton(
                "📊 Статистика",
                callback_data="admin_stats"
            )
        )

        markup.row(
            types.InlineKeyboardButton(
                "📢 Рассылка",
                callback_data="admin_broadcast"
            )
        )

        bot.send_message(
            message.chat.id,
            "⚙️ ADMIN PANEL",
            reply_markup=markup
        )

    # USERS
    @bot.callback_query_handler(func=lambda c: c.data == "admin_users")
    def users(call):

        if call.from_user.id not in ADMIN_ID:
            return

        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()

        if not users:
            bot.send_message(call.message.chat.id, "Нет пользователей")
            return

        user_ids = [str(user[0]) for user in users]

        text = "👥 Пользователи:\n\n" + "\n".join(user_ids)

        # если слишком длинное сообщение — режем
        if len(text) > 4000:
            for i in range(0, len(user_ids), 100):
                chunk = "\n".join(user_ids[i:i + 100])
                bot.send_message(call.message.chat.id, chunk)
        else:
            bot.send_message(call.message.chat.id, text)

        bot.send_message(
            call.message.chat.id,
            "\nОтправь ID пользователя для управления"
        )

        bot.register_next_step_handler(
            call.message,
            user_manage
        )

    def user_manage(message):

        if message.from_user.id not in ADMIN_ID:
            return

        try:
            user_id = int(message.text)
        except:
            bot.send_message(message.chat.id, "ID неверный")
            return

        markup = types.InlineKeyboardMarkup()

        markup.row(
            types.InlineKeyboardButton(
                "✅ Выдать 30 дней",
                callback_data=f"give_{user_id}"
            ),
            types.InlineKeyboardButton(
                "❌ Забрать",
                callback_data=f"remove_{user_id}"
            )
        )

        bot.send_message(
            message.chat.id,
            f"Управление пользователем {user_id}",
            reply_markup=markup
        )

    # GIVE SUB

    @bot.callback_query_handler(func=lambda c: c.data.startswith("give_"))
    def give(call):

        if call.from_user.id not in ADMIN_ID:
            return

        user_id = int(call.data.split("_")[1])

        set_subscription(user_id, 30)

        bot.send_message(user_id, "✅ Админ выдал подписку")

        bot.answer_callback_query(call.id, "Выдано")

    # REMOVE SUB
    @bot.callback_query_handler(func=lambda c: c.data.startswith("remove_"))
    def remove(call):

        if call.from_user.id not in ADMIN_ID:
            return

        cursor.execute("""
        UPDATE users SET sub_until=0 WHERE user_id=?
        """, (int(call.data.split("_")[1]),))

        conn.commit()

        bot.answer_callback_query(call.id, "Удалено")

    # STATS
    @bot.callback_query_handler(func=lambda c: c.data == "admin_stats")
    def stats(call):

        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]

        cursor.execute("""
        SELECT COUNT(*) FROM users
        WHERE sub_until > ?
        """, (int(time.time()),))

        active = cursor.fetchone()[0]

        bot.send_message(
            call.message.chat.id,
            f"""
📊 Статистика

👥 Пользователей: {total}
💎 Активных: {active}
"""
        )

    # BROADCAST
    @bot.callback_query_handler(func=lambda c: c.data == "admin_broadcast")
    def broadcast(call):

        bot.send_message(
            call.message.chat.id,
            "Отправь текст рассылки"
        )

        bot.register_next_step_handler(
            call.message,
            send_broadcast
        )

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

        bot.send_message(
            message.chat.id,
            f"✅ Отправлено: {sent}"
        )