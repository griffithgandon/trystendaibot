from telebot import types
import time

from config import (
    ADMIN_ID,
    PAYMENT_TEXT,
    TARIFFS
)

from database.db import *
from services.vpn import create_user, get_vpn_data
from services.vpn import create_user, get_vpn_data
from utils.qr import generate_qr


# ===== UI =====
def get_main_menu(user_id):

    markup = types.InlineKeyboardMarkup(row_width=2)

    markup.add(
        types.InlineKeyboardButton(
            "👤 Профиль",
            callback_data="profile"
        ),

        types.InlineKeyboardButton(
            "💎 Купить VPN",
            callback_data="buy"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "🔑 Мой VPN",
            callback_data="token"
        ),

        types.InlineKeyboardButton(
            "💬 Поддержка",
            callback_data="support"
        )
    )

    if user_id in ADMIN_ID:

        markup.add(
            types.InlineKeyboardButton(
                "⚙️ Админ",
                callback_data="admin_panel"
            )
        )

    return markup


def back_button():

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "⬅️ Назад",
            callback_data="menu"
        )
    )

    return markup


# ===== SAFE EDIT =====
def safe_edit(bot, call, text, markup=None):

    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )

    except Exception as e:
        print("SAFE EDIT ERROR:", e)


# ===== HANDLERS =====
def register_handlers(bot):

    # ===== START =====
    @bot.message_handler(commands=["start"])
    def start(message):

        try:
            user_id = message.from_user.id

            add_user(
                user_id,
                message.from_user.username
            )
            # ===== TG USERNAME =====
            telegram_username = message.from_user.username

            if telegram_username:
                cursor.execute(
                    """
                    UPDATE users
                    SET telegram_username=?
                    WHERE user_id = ?
                    """,
                    (
                        telegram_username,
                        user_id
                    )
                )

                conn.commit()

            # ===== ПРОВЕРКА НИКА =====
            if get_username(user_id):

                bot.send_message(
                    message.chat.id,
                    "📱 Главное меню:",
                    reply_markup=get_main_menu(user_id)
                )

            else:

                msg = bot.send_message(
                    message.chat.id,
                    "👋 Введи свой ник:"
                )

                bot.register_next_step_handler(
                    msg,
                    save_name
                )

        except Exception as e:
            print("START ERROR:", e)

    # ===== SAVE NAME =====
    def save_name(message):

        try:
            user_id = message.from_user.id
            username = message.text.strip()

            if len(username) < 2:

                msg = bot.send_message(
                    message.chat.id,
                    "❌ Ник слишком короткий"
                )

                bot.register_next_step_handler(
                    msg,
                    save_name
                )

                return

            save_username(user_id, username)

            bot.send_message(
                message.chat.id,
                f"✅ Ник сохранён: {username}",
                reply_markup=get_main_menu(user_id)
            )

        except Exception as e:
            print("SAVE NAME ERROR:", e)

    # ===== MENU =====
    @bot.callback_query_handler(func=lambda c: c.data == "menu")
    def menu(call):

        bot.answer_callback_query(call.id)

        safe_edit(
            bot,
            call,
            "📱 Главное меню:",
            get_main_menu(call.from_user.id)
        )

    # ===== PROFILE =====
    @bot.callback_query_handler(func=lambda c: c.data == "profile")
    def profile(call):

        try:
            bot.answer_callback_query(call.id)

            user_id = call.from_user.id

            username = get_username(user_id) or "—"

            sub_until = get_sub_until(user_id)

            if sub_until > int(time.time()):

                date = time.strftime(
                    "%d.%m.%Y %H:%M",
                    time.localtime(sub_until)
                )

                status = f"✅ До {date}"

            else:
                status = "❌ Нет"

            text = f"""
👤 Профиль

🆔 ID: {user_id}
👤 Ник: {username}
💎 Подписка: {status}
"""

            safe_edit(
                bot,
                call,
                text,
                back_button()
            )

        except Exception as e:
            print("PROFILE ERROR:", e)

    # ===== BUY =====
    @bot.callback_query_handler(func=lambda c: c.data == "buy")
    def buy(call):

        try:
            bot.answer_callback_query(call.id)

            markup = types.InlineKeyboardMarkup(row_width=1)

            for tariff_id, tariff in TARIFFS.items():

                markup.add(
                    types.InlineKeyboardButton(
                        tariff.get("title", "Тариф"),
                        callback_data=f"tariff_{tariff_id}"
                    )
                )

            markup.add(
                types.InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data="menu"
                )
            )

            safe_edit(
                bot,
                call,
                "💎 Выбери тариф:",
                markup
            )

        except Exception as e:
            print("BUY ERROR:", e)

    # ===== TARIFF =====
    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("tariff_")
    )
    def tariff(call):

        try:
            bot.answer_callback_query(call.id)

            tariff_id = call.data.split("_")[1]

            tariff = TARIFFS.get(tariff_id)

            if not tariff:
                return

            text = f"""
{PAYMENT_TEXT}

📦 Тариф: {tariff.get("title")}
💰 Цена: {tariff.get("price")}₽
📅 Срок: {tariff.get("days")} дней

🆔 Ваш ID:
{call.from_user.id}
"""

            markup = types.InlineKeyboardMarkup(row_width=1)

            markup.add(
                types.InlineKeyboardButton(
                    "✅ Я оплатил",
                    callback_data=f"paid_{tariff_id}"
                )
            )

            markup.add(
                types.InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data="buy"
                )
            )

            safe_edit(
                bot,
                call,
                text,
                markup
            )

        except Exception as e:
            print("TARIFF ERROR:", e)

    # ===== PAID =====
    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("paid_")
    )
    def paid(call):

        try:
            bot.answer_callback_query(call.id)

            tariff_id = call.data.split("_")[1]

            tariff = TARIFFS.get(tariff_id)

            if not tariff:
                return

            user_id = call.from_user.id

            if has_pending_payment(user_id):

                bot.answer_callback_query(
                    call.id,
                    "⏳ У тебя уже есть заявка"
                )

                return

            add_pending_payment(
                user_id,
                tariff_id
            )

            username = get_username(user_id) or "Без ника"

            markup = types.InlineKeyboardMarkup()

            markup.add(
                types.InlineKeyboardButton(
                    "✅ Подтвердить",
                    callback_data=f"approve_{user_id}_{tariff_id}"
                )
            )

            for admin in ADMIN_ID:

                bot.send_message(
                    admin,
                    f"""
💰 Новая заявка

👤 Пользователь: {username}
🆔 ID: {user_id}

📦 Тариф: {tariff.get("title")}
💰 Сумма: {tariff.get("price")}₽
""",
                    reply_markup=markup
                )

            safe_edit(
                bot,
                call,
                """
✅ Заявка отправлена

⏳ Ожидайте подтверждения
""",
                back_button()
            )

        except Exception as e:
            print("PAID ERROR:", e)

    # ===== APPROVE =====
    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("approve_")
    )
    def approve(call):

        try:
            if call.from_user.id not in ADMIN_ID:
                return

            _, user_id, tariff_id = call.data.split("_")

            user_id = int(user_id)

            tariff = TARIFFS.get(tariff_id)

            if not tariff:
                return

            days = tariff.get("days", 30)

            set_subscription(user_id, days)

            create_user(user_id, days)

            remove_pending_payment(user_id)

            bot.send_message(
                user_id,
                f"""
✅ Оплата подтверждена

📦 Тариф: {tariff.get("title")}
📅 Срок: {days} дней

🔑 VPN активирован
"""
            )

            safe_edit(
                bot,
                call,
                "✅ Оплата подтверждена",
                back_button()
            )

            bot.answer_callback_query(
                call.id,
                "✅ Готово"
            )

        except Exception as e:
            print("APPROVE ERROR:", e)

    # ===== SUPPORT =====
    @bot.callback_query_handler(
        func=lambda c: c.data == "support"
    )
    def support(call):

        try:
            bot.answer_callback_query(call.id)

            msg = bot.send_message(
                call.message.chat.id,
                """
💬 Поддержка

Напиши сообщение администрации:
"""
            )

            bot.register_next_step_handler(
                msg,
                send_support
            )

        except Exception as e:
            print("SUPPORT ERROR:", e)

    # ===== SEND SUPPORT =====
    def send_support(message):

        try:
            user_id = message.from_user.id

            username = (
                get_username(user_id)
                or "Без ника"
            )

            text = message.text

            markup = types.InlineKeyboardMarkup()

            markup.add(
                types.InlineKeyboardButton(
                    "✉️ Ответить",
                    callback_data=f"reply_{user_id}"
                )
            )

            for admin in ADMIN_ID:

                bot.send_message(
                    admin,
                    f"""
💬 Новое сообщение

👤 Пользователь: {username}
🆔 ID: {user_id}

📩 Сообщение:
{text}
""",
                    reply_markup=markup
                )

            bot.send_message(
                user_id,
                "✅ Сообщение отправлено"
            )

        except Exception as e:
            print("SEND SUPPORT ERROR:", e)

    # ===== REPLY =====
    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("reply_")
    )
    def reply(call):

        try:
            if call.from_user.id not in ADMIN_ID:
                return

            bot.answer_callback_query(call.id)

            user_id = int(
                call.data.split("_")[1]
            )

            msg = bot.send_message(
                call.message.chat.id,
                f"✉️ Ответ пользователю {user_id}:"
            )

            bot.register_next_step_handler(
                msg,
                lambda m: send_reply(
                    m,
                    user_id
                )
            )

        except Exception as e:
            print("REPLY ERROR:", e)

    # ===== SEND REPLY =====
    def send_reply(message, user_id):

        try:
            bot.send_message(
                user_id,
                f"""
💬 Ответ поддержки

{message.text}
"""
            )

            bot.send_message(
                message.chat.id,
                "✅ Ответ отправлен"
            )

        except Exception as e:
            print("SEND REPLY ERROR:", e)

    # ===== TOKEN =====
    @bot.callback_query_handler(
        func=lambda c: c.data == "token"
    )
    def token(call):

        try:
            bot.answer_callback_query(call.id)

            user_id = call.from_user.id

            if not has_sub(user_id):

                bot.answer_callback_query(
                    call.id,
                    "❌ Нет подписки"
                )

                return

            sub = get_vpn_data(user_id)

            if not sub:
                return

            text = f"""
🔑 Твой VPN

{sub}
"""

            safe_edit(
                bot,
                call,
                text,
                back_button()
            )

            qr = generate_qr(sub)

            bot.send_photo(
                call.message.chat.id,
                qr
            )

        except Exception as e:
            print("TOKEN ERROR:", e)