from telebot import types
from config import ADMIN_ID
from database.db import set_subscription, conn, cursor
from services.vpn import create_user, delete_user
import time


def is_admin(user_id):
    return user_id in ADMIN_ID


# ===== SAFE EDIT (фикс ошибки message is not modified) =====
def safe_edit(bot, call, text, markup):
    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
    except Exception as e:
        if "message is not modified" not in str(e):
            print("EDIT ERROR:", e)


# ===== UI =====
def admin_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("⬅️ Назад", callback_data="menu")
    )
    return markup


def back():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
    return markup


# ===== HANDLERS =====
def register_admin(bot):

    # ===== ПАНЕЛЬ =====
    @bot.callback_query_handler(func=lambda c: c.data == "admin_panel")
    def admin_panel(call):
        if not is_admin(call.from_user.id):
            return

        bot.answer_callback_query(call.id)

        safe_edit(bot, call, "⚙️ Админ панель", admin_menu())


    # ===== ПОЛЬЗОВАТЕЛИ =====
    @bot.callback_query_handler(func=lambda c: c.data == "admin_users")
    def users(call):
        if not is_admin(call.from_user.id):
            return

        bot.answer_callback_query(call.id)

        cursor.execute("SELECT user_id FROM users ORDER BY user_id DESC LIMIT 20")
        rows = cursor.fetchall()

        markup = types.InlineKeyboardMarkup()

        for u in rows:
            user_id = u[0]
            markup.add(
                types.InlineKeyboardButton(
                    f"👤 {user_id}",
                    callback_data=f"user_{user_id}"
                )
            )

        markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))

        safe_edit(bot, call, "👥 Последние пользователи:", markup)


    # ===== ПОЛЬЗОВАТЕЛЬ =====
    @bot.callback_query_handler(func=lambda c: c.data.startswith("user_"))
    def user_menu(call):
        if not is_admin(call.from_user.id):
            return

        bot.answer_callback_query(call.id)

        user_id = int(call.data.split("_")[1])

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Выдать", callback_data=f"give_{user_id}"),
            types.InlineKeyboardButton("❌ Удалить", callback_data=f"remove_{user_id}")
        )
        markup.add(
            types.InlineKeyboardButton("♻️ Пересоздать", callback_data=f"recreate_{user_id}")
        )
        markup.add(
            types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_users")
        )

        safe_edit(bot, call, f"👤 Пользователь: {user_id}", markup)


    # ===== ВЫДАТЬ =====
    @bot.callback_query_handler(func=lambda c: c.data.startswith("give_"))
    def give(call):
        if not is_admin(call.from_user.id):
            return

        bot.answer_callback_query(call.id)

        user_id = int(call.data.split("_")[1])

        try:
            set_subscription(user_id, 30)
            create_user(user_id, 30)

            safe_edit(bot, call, f"✅ Выдано {user_id}", back())

            bot.send_message(user_id, "✅ Подписка выдана")

        except Exception as e:
            print("GIVE ERROR:", e)


    # ===== УДАЛИТЬ (ПОЛНЫЙ ФИКС) =====
    @bot.callback_query_handler(func=lambda c: c.data.startswith("remove_"))
    def remove(call):
        if not is_admin(call.from_user.id):
            return

        bot.answer_callback_query(call.id)

        user_id = int(call.data.split("_")[1])

        try:
            print("DELETE USER:", user_id)

            result = delete_user(user_id)
            print("DELETE RESULT:", result)

            # даже если API упал — обнуляем базу
            cursor.execute(
                "UPDATE users SET sub_until = 0 WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()

            safe_edit(bot, call, f"❌ Пользователь {user_id} удалён", back())

            try:
                bot.send_message(user_id, "❌ Подписка удалена")
            except:
                pass

        except Exception as e:
            print("DELETE ERROR:", e)


    # ===== ПЕРЕСОЗДАТЬ =====
    @bot.callback_query_handler(func=lambda c: c.data.startswith("recreate_"))
    def recreate(call):
        if not is_admin(call.from_user.id):
            return

        bot.answer_callback_query(call.id)

        user_id = int(call.data.split("_")[1])

        try:
            delete_user(user_id)
            set_subscription(user_id, 30)
            create_user(user_id, 30)

            safe_edit(bot, call, f"♻️ Пересоздан {user_id}", back())

            bot.send_message(user_id, "♻️ VPN пересоздан")

        except Exception as e:
            print("RECREATE ERROR:", e)


    # ===== СТАТИСТИКА =====
    @bot.callback_query_handler(func=lambda c: c.data == "admin_stats")
    def stats(call):
        if not is_admin(call.from_user.id):
            return

        bot.answer_callback_query(call.id)

        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE sub_until > ?",
            (int(time.time()),)
        )
        active = cursor.fetchone()[0]

        safe_edit(
            bot,
            call,
            f"📊 Статистика\n\n👥 Всего: {total}\n💎 Активных: {active}",
            back()
        )


    # ===== РАССЫЛКА =====
    @bot.callback_query_handler(func=lambda c: c.data == "admin_broadcast")
    def broadcast(call):
        if not is_admin(call.from_user.id):
            return

        bot.answer_callback_query(call.id)

        msg = bot.send_message(call.message.chat.id, "✍️ Введи текст")
        bot.register_next_step_handler(msg, send_broadcast)


    def send_broadcast(message):
        if not is_admin(message.from_user.id):
            return

        cursor.execute("SELECT user_id FROM users")
        rows = cursor.fetchall()

        sent = 0

        for u in rows:
            try:
                bot.send_message(u[0], message.text)
                sent += 1
            except:
                pass

        bot.send_message(message.chat.id, f"✅ Отправлено: {sent}")