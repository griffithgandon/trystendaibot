from telebot import types
from config import ADMIN_ID
from database.db import *
from services.vpn import create_user, delete_user
import time


def is_admin(user_id):
    return user_id in ADMIN_ID


# ===== SAFE EDIT =====
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
        types.InlineKeyboardButton(
            "👥 Пользователи",
            callback_data="admin_users"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "💰 Заявки",
            callback_data="pending_list"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "📊 Статистика",
            callback_data="admin_stats"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "📢 Рассылка",
            callback_data="admin_broadcast"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "⬅️ Назад",
            callback_data="menu"
        )
    )

    return markup


def back():
    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "⬅️ Назад",
            callback_data="admin_panel"
        )
    )

    return markup


# ===== HANDLERS =====
def register_admin_handlers(bot):

    # ===== ADMIN PANEL =====
    @bot.callback_query_handler(
        func=lambda c: c.data == "admin_panel"
    )
    def admin_panel(call):

        if not is_admin(call.from_user.id):
            return

        bot.answer_callback_query(call.id)

        safe_edit(
            bot,
            call,
            "⚙️ Админ панель",
            admin_menu()
        )

    # ===== USERS =====
    @bot.callback_query_handler(
        func=lambda c: c.data == "admin_users"
    )
    def users(call):

        if not is_admin(call.from_user.id):
            return

        bot.answer_callback_query(call.id)

        cursor.execute(
            "SELECT user_id FROM users ORDER BY user_id DESC LIMIT 20"
        )

        rows = cursor.fetchall()

        markup = types.InlineKeyboardMarkup()

        for u in rows:

            user_id = u[0]

            username = get_username(user_id)

            if not username:
                username = "Без ника"

            markup.add(
                types.InlineKeyboardButton(
                    f"👤 {username} | {user_id}",
                    callback_data=f"user_{user_id}"
                )
            )

        markup.add(
            types.InlineKeyboardButton(
                "⬅️ Назад",
                callback_data="admin_panel"
            )
        )

        safe_edit(
            bot,
            call,
            "👥 Последние пользователи:",
            markup
        )

    # ===== USER MENU =====
    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("user_")
    )
    def user_menu(call):

        if not is_admin(call.from_user.id):
            return

        bot.answer_callback_query(call.id)

        user_id = int(call.data.split("_")[1])

        username = get_username(user_id) or "—"

        tg_username = (
                get_telegram_username(user_id)
                or "нет"
        )

        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "✅ Выдать",
                callback_data=f"give_{user_id}"
            ),

            types.InlineKeyboardButton(
                "❌ Удалить",
                callback_data=f"remove_{user_id}"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "♻️ Пересоздать",
                callback_data=f"recreate_{user_id}"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "⬅️ Назад",
                callback_data="admin_users"
            )
        )

        username = get_username(user_id)

        sub_until = get_sub_until(user_id)

        if sub_until > int(time.time()):
            sub_text = time.strftime(
                "%d.%m.%Y %H:%M",
                time.localtime(sub_until)
            )
        else:
            sub_text = "Нет подписки"

        if not username:
            username = "Без ника"

        text = f"""
        👤 Пользователь

        🪪 Ник: {username}
        🌐 Telegram: @{tg_username}
        🆔 ID: {user_id}

        💎 Подписка:
        {sub_text}
        """
        
        safe_edit(
            bot,
            call,
            text,
            markup
        )

    # ===== GIVE =====
    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("give_")
    )
    def give(call):

        if not is_admin(call.from_user.id):
            return

        bot.answer_callback_query(call.id)

        user_id = int(call.data.split("_")[1])

        try:

            set_subscription(user_id, 30)

            create_user(user_id, 30)

            safe_edit(
                bot,
                call,
                f"✅ Выдано {user_id}",
                back()
            )

            bot.send_message(
                user_id,
                "✅ Подписка выдана"
            )

        except Exception as e:
            print("GIVE ERROR:", e)

    # ===== REMOVE =====
    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("remove_")
    )
    def remove(call):

        if not is_admin(call.from_user.id):
            return

        bot.answer_callback_query(call.id)

        user_id = int(call.data.split("_")[1])

        try:

            delete_user(user_id)

            cursor.execute(
                "UPDATE users SET sub_until = 0 WHERE user_id = ?",
                (user_id,)
            )

            conn.commit()

            safe_edit(
                bot,
                call,
                f"❌ Пользователь {user_id} удалён",
                back()
            )

            try:
                bot.send_message(
                    user_id,
                    "❌ Ваша подписка удалена"
                )
            except:
                pass

        except Exception as e:
            print("DELETE ERROR:", e)

    # ===== RECREATE =====
    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("recreate_")
    )
    def recreate(call):

        if not is_admin(call.from_user.id):
            return

        bot.answer_callback_query(call.id)

        user_id = int(call.data.split("_")[1])

        try:

            delete_user(user_id)

            set_subscription(user_id, 30)

            create_user(user_id, 30)

            safe_edit(
                bot,
                call,
                f"♻️ Пересоздан {user_id}",
                back()
            )

            bot.send_message(
                user_id,
                "♻️ VPN пересоздан"
            )

        except Exception as e:
            print("RECREATE ERROR:", e)

    # ===== STATS =====
    @bot.callback_query_handler(
        func=lambda c: c.data == "admin_stats"
    )
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
            f"""
📊 Статистика

👥 Всего пользователей: {total}
💎 Активных подписок: {active}
""",
            back()
        )

    # ===== PENDING PAYMENTS =====
    @bot.callback_query_handler(
        func=lambda c: c.data == "pending_list"
    )
    def pending_list(call):

        if not is_admin(call.from_user.id):
            return

        bot.answer_callback_query(call.id)

        payments = get_pending_payments()

        if not payments:

            safe_edit(
                bot,
                call,
                "❌ Активных заявок нет",
                back()
            )

            return

        markup = types.InlineKeyboardMarkup()

        text = "💰 Активные заявки\n"

        for user_id, tariff_id, created_at in payments:

            username = get_username(user_id) or "Без ника"

            text += f"""

👤 {username}
🆔 ID: {user_id}
"""

            markup.add(
                types.InlineKeyboardButton(
                    f"👤 {user_id}",
                    callback_data=f"user_{user_id}"
                )
            )

        markup.add(
            types.InlineKeyboardButton(
                "⬅️ Назад",
                callback_data="admin_panel"
            )
        )

        safe_edit(
            bot,
            call,
            text,
            markup
        )

    # ===== BROADCAST =====
    @bot.callback_query_handler(
        func=lambda c: c.data == "admin_broadcast"
    )
    def broadcast(call):

        if not is_admin(call.from_user.id):
            return

        bot.answer_callback_query(call.id)

        msg = bot.send_message(
            call.message.chat.id,
            "✍️ Введи текст рассылки"
        )

        bot.register_next_step_handler(
            msg,
            send_broadcast
        )

    def send_broadcast(message):

        if not is_admin(message.from_user.id):
            return

        cursor.execute(
            "SELECT user_id FROM users"
        )

        rows = cursor.fetchall()

        sent = 0

        for u in rows:

            try:

                bot.send_message(
                    u[0],
                    message.text
                )

                sent += 1

            except:
                pass

        bot.send_message(
            message.chat.id,
            f"✅ Отправлено: {sent}"
        )