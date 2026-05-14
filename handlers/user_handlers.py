from telebot import types
import time
import requests
import json
from config import (
    ADMIN_ID,
    PAYMENT_TEXT,
    TARIFFS,
    PANEL_URL,
    API_TOKEN,
    SERVERS,  # добавить
)


from config import (
    ADMIN_ID,
    PAYMENT_TEXT,
    TARIFFS,
    PANEL_URL,
    API_TOKEN
)

from database.db import (
    add_user, get_username, save_username,
    get_sub_until, has_sub, has_pending_payment,
    add_pending_payment, remove_pending_payment,
    get_telegram_username, get_pending_payment_type,
)

from services.vpn import create_user, get_vpn_data, extend_user
from utils.qr import generate_qr
from utils.rate_limiter import rate_limit, payment_limiter, support_limiter, start_limiter


# ===== UI =====
def get_main_menu(user_id: int) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)

    markup.add(
        types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        types.InlineKeyboardButton("💎 Купить VPN", callback_data="buy")
    )
    markup.add(
        types.InlineKeyboardButton("🔑 Мой VPN", callback_data="token"),
        types.InlineKeyboardButton("💬 Поддержка", callback_data="support")
    )

    if has_sub(user_id):
        markup.add(
            types.InlineKeyboardButton("🔄 Продлить", callback_data="renew")
        )

    markup.add(
        types.InlineKeyboardButton("🖥 Статус сервера", callback_data="server_status")
    )

    if user_id in ADMIN_ID:
        markup.add(
            types.InlineKeyboardButton("⚙️ Админ", callback_data="admin_panel")
        )

    return markup


def back_button() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu"))
    return markup


def safe_edit(bot, call, text: str, markup=None):
    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
    except Exception as e:
        if "message is not modified" not in str(e):
            print("SAFE EDIT ERROR:", e)


# ===== HANDLERS =====
def register_handlers(bot):

    # ===== START =====
    @bot.message_handler(commands=["start"])
    def start(message):
        if not rate_limit(bot, message, start_limiter):
            return

        try:
            user_id = message.from_user.id
            tg_username = message.from_user.username

            add_user(user_id, tg_username)

            if get_username(user_id):
                bot.send_message(
                    message.chat.id,
                    "📱 Главное меню:",
                    reply_markup=get_main_menu(user_id)
                )
            else:
                msg = bot.send_message(message.chat.id, "👋 Введи свой ник:")
                bot.register_next_step_handler(msg, save_name)

        except Exception as e:
            print("START ERROR:", e)

    # ===== SAVE NAME =====
    def save_name(message):
        try:
            user_id = message.from_user.id
            username = message.text.strip()

            # Валидация длины и содержимого
            if len(username) < 2 or len(username) > 32:
                msg = bot.send_message(
                    message.chat.id,
                    "❌ Ник должен быть от 2 до 32 символов"
                )
                bot.register_next_step_handler(msg, save_name)
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
        if not rate_limit(bot, call):
            return

        bot.answer_callback_query(call.id)
        safe_edit(bot, call, "📱 Главное меню:", get_main_menu(call.from_user.id))

    # ===== PROFILE =====
    @bot.callback_query_handler(func=lambda c: c.data == "profile")
    def profile(call):
        if not rate_limit(bot, call):
            return

        try:
            bot.answer_callback_query(call.id)
            user_id = call.from_user.id
            username = get_username(user_id) or "—"
            sub_until = get_sub_until(user_id)

            if sub_until > int(time.time()):
                date = time.strftime("%d.%m.%Y %H:%M", time.localtime(sub_until))
                status = f"✅ До {date}"
            else:
                status = "❌ Нет"

            safe_edit(
                bot, call,
                f"👤 Профиль\n\n🆔 ID: {user_id}\n👤 Ник: {username}\n💎 Подписка: {status}",
                back_button()
            )

        except Exception as e:
            print("PROFILE ERROR:", e)

    # Добавить хендлеры продления внутри register_handlers(bot):

    # ===== RENEW =====
    @bot.callback_query_handler(func=lambda c: c.data == "renew")
    def renew(call):
        if not rate_limit(bot, call):
            return

        try:
            bot.answer_callback_query(call.id)

            if not has_sub(call.from_user.id):
                bot.answer_callback_query(call.id, "❌ Нет активной подписки", show_alert=True)
                return

            markup = types.InlineKeyboardMarkup(row_width=1)

            for tariff_id, tariff in TARIFFS.items():
                markup.add(
                    types.InlineKeyboardButton(
                        tariff.get("title", "Тариф"),
                        callback_data=f"renew_tariff_{tariff_id}"
                    )
                )

            markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu"))
            safe_edit(bot, call, "🔄 Продление подписки\n\nВыбери тариф:", markup)

        except Exception as e:
            print("RENEW ERROR:", e)

    # ===== RENEW TARIFF =====
    @bot.callback_query_handler(func=lambda c: c.data.startswith("renew_tariff_"))
    def renew_tariff(call):
        if not rate_limit(bot, call):
            return

        try:
            bot.answer_callback_query(call.id)

            tariff_id = call.data[len("renew_tariff_"):]
            tariff = TARIFFS.get(tariff_id)
            if not tariff:
                return

            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("✅ Я оплатил", callback_data=f"renew_paid_{tariff_id}")
            )
            markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="renew"))

            sub_until = get_sub_until(call.from_user.id)
            date = time.strftime("%d.%m.%Y", time.localtime(sub_until))

            text = (
                f"{PAYMENT_TEXT}\n\n"
                f"🔄 Продление подписки\n"
                f"📅 Текущая подписка до: {date}\n\n"
                f"📦 Тариф: {tariff.get('title')}\n"
                f"💰 Цена: {tariff.get('price')}₽\n"
                f"📅 Добавится: {tariff.get('days')} дней\n\n"
                f"🆔 Ваш ID:\n{call.from_user.id}"
            )

            safe_edit(bot, call, text, markup)

        except Exception as e:
            print("RENEW TARIFF ERROR:", e)

    # ===== RENEW PAID =====
    @bot.callback_query_handler(func=lambda c: c.data.startswith("renew_paid_"))
    def renew_paid(call):
        if not rate_limit(bot, call, payment_limiter):
            return

        try:
            bot.answer_callback_query(call.id)

            tariff_id = call.data[len("renew_paid_"):]
            tariff = TARIFFS.get(tariff_id)
            if not tariff:
                return

            user_id = call.from_user.id

            if has_pending_payment(user_id):
                bot.answer_callback_query(
                    call.id,
                    "⏳ У тебя уже есть активная заявка",
                    show_alert=True
                )
                return

            add_pending_payment(user_id, tariff_id, payment_type="renew")

            username = get_username(user_id) or "Без ника"
            sub_until = get_sub_until(user_id)
            date = time.strftime("%d.%m.%Y", time.localtime(sub_until))

            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "✅ Подтвердить продление",
                    callback_data=f"approve|{user_id}|{tariff_id}"
                )
            )

            for admin in ADMIN_ID:
                try:
                    bot.send_message(
                        admin,
                        f"🔄 Заявка на продление\n\n"
                        f"👤 {username}\n"
                        f"🆔 ID: {user_id}\n"
                        f"📅 Подписка до: {date}\n\n"
                        f"📦 Тариф: {tariff.get('title')}\n"
                        f"💰 Сумма: {tariff.get('price')}₽",
                        reply_markup=markup
                    )
                except Exception:
                    pass

            safe_edit(
                bot, call,
                "✅ Заявка на продление отправлена\n\n⏳ Ожидайте подтверждения",
                back_button()
            )

        except Exception as e:
            print("RENEW PAID ERROR:", e)

    # ===== BUY =====
    @bot.callback_query_handler(func=lambda c: c.data == "buy")
    def buy(call):
        if not rate_limit(bot, call):
            return

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

            markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu"))
            safe_edit(bot, call, "💎 Выбери тариф:", markup)

        except Exception as e:
            print("BUY ERROR:", e)

    # ===== TARIFF =====
    @bot.callback_query_handler(func=lambda c: c.data.startswith("tariff_"))
    def tariff(call):
        if not rate_limit(bot, call):
            return

        try:
            bot.answer_callback_query(call.id)

            # Безопасный парсинг: берём только первую часть после "tariff_"
            tariff_id = call.data[len("tariff_"):]

            tariff = TARIFFS.get(tariff_id)
            if not tariff:
                return

            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("✅ Я оплатил", callback_data=f"paid_{tariff_id}")
            )
            markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="buy"))

            text = (
                f"{PAYMENT_TEXT}\n\n"
                f"📦 Тариф: {tariff.get('title')}\n"
                f"💰 Цена: {tariff.get('price')}₽\n"
                f"📅 Срок: {tariff.get('days')} дней\n\n"
                f"🆔 Ваш ID:\n{call.from_user.id}"
            )

            safe_edit(bot, call, text, markup)

        except Exception as e:
            print("TARIFF ERROR:", e)

    # ===== PAID =====
    @bot.callback_query_handler(func=lambda c: c.data.startswith("paid_"))
    def paid(call):
        # Строгий лимит на платёжные заявки
        if not rate_limit(bot, call, payment_limiter):
            return

        try:
            bot.answer_callback_query(call.id)

            tariff_id = call.data[len("paid_"):]
            tariff = TARIFFS.get(tariff_id)
            if not tariff:
                return

            user_id = call.from_user.id

            if has_pending_payment(user_id):
                bot.answer_callback_query(
                    call.id,
                    "⏳ У тебя уже есть активная заявка",
                    show_alert=True
                )
                return

            add_pending_payment(user_id, tariff_id)

            username = get_username(user_id) or "Без ника"

            markup = types.InlineKeyboardMarkup()
            # Используем | как разделитель вместо _ чтобы tariff_id не ломал split
            markup.add(
                types.InlineKeyboardButton(
                    "✅ Подтвердить",
                    callback_data=f"approve|{user_id}|{tariff_id}"
                )
            )

            for admin in ADMIN_ID:
                try:
                    bot.send_message(
                        admin,
                        f"💰 Новая заявка\n\n"
                        f"👤 {username}\n"
                        f"🆔 ID: {user_id}\n\n"
                        f"📦 Тариф: {tariff.get('title')}\n"
                        f"💰 Сумма: {tariff.get('price')}₽",
                        reply_markup=markup
                    )
                except Exception:
                    pass

            safe_edit(
                bot, call,
                "✅ Заявка отправлена\n\n⏳ Ожидайте подтверждения",
                back_button()
            )

        except Exception as e:
            print("PAID ERROR:", e)

    # ===== APPROVE =====
    # Заменить хендлер approve:
    @bot.callback_query_handler(func=lambda c: c.data.startswith("approve|"))
    def approve(call):
        try:
            if call.from_user.id not in ADMIN_ID:
                return

            parts = call.data.split("|")
            if len(parts) != 3:
                return

            _, user_id_str, tariff_id = parts
            user_id = int(user_id_str)

            tariff = TARIFFS.get(tariff_id)
            if not tariff:
                return

            days = tariff.get("days", 30)

            from database.db import set_subscription
            payment_type = get_pending_payment_type(user_id)

            set_subscription(user_id, days)

            if payment_type == "renew":
                extend_user(user_id, days)
            else:
                create_user(user_id, days)

            remove_pending_payment(user_id)

            type_label = "🔄 Продление" if payment_type == "renew" else "✅ Оплата"

            try:
                bot.send_message(
                    user_id,
                    f"{type_label} подтверждено\n\n"
                    f"📦 Тариф: {tariff.get('title')}\n"
                    f"📅 Добавлено: {days} дней\n\n"
                    f"🔑 VPN {'продлён' if payment_type == 'renew' else 'активирован'}"
                )
            except Exception:
                pass

            safe_edit(bot, call, f"{type_label} подтверждено", back_button())
            bot.answer_callback_query(call.id, "✅ Готово")

        except Exception as e:
            print("APPROVE ERROR:", e)

    # ===== SUPPORT =====
    @bot.callback_query_handler(func=lambda c: c.data == "support")
    def support(call):
        if not rate_limit(bot, call, support_limiter):
            return

        try:
            bot.answer_callback_query(call.id)
            msg = bot.send_message(
                call.message.chat.id,
                "💬 Напиши сообщение и мы ответим:"
            )
            bot.register_next_step_handler(msg, send_support)

        except Exception as e:
            print("SUPPORT ERROR:", e)

    # ===== SEND SUPPORT =====
    def send_support(message):
        # Ограничение длины сообщения
        if not rate_limit(bot, message, support_limiter):
            return

        try:
            user_id = message.from_user.id
            text = message.text

            if not text:
                bot.send_message(message.chat.id, "❌ Пустое сообщение")
                return

            # Обрезаем слишком длинные сообщения
            if len(text) > 1000:
                text = text[:1000] + "...\n[обрезано]"

            username = get_username(user_id) or "Без ника"

            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "✉️ Ответить",
                    callback_data=f"reply|{user_id}"
                )
            )

            for admin in ADMIN_ID:
                try:
                    bot.send_message(
                        admin,
                        f"💬 Новое сообщение\n\n"
                        f"👤 {username}\n"
                        f"🆔 ID: {user_id}\n\n"
                        f"📩 Сообщение:\n{text}",
                        reply_markup=markup
                    )
                except Exception:
                    pass

            bot.send_message(user_id, "✅ Сообщение отправлено")

        except Exception as e:
            print("SEND SUPPORT ERROR:", e)

    # ===== REPLY =====
    @bot.callback_query_handler(func=lambda c: c.data.startswith("reply|"))
    def reply(call):
        try:
            if call.from_user.id not in ADMIN_ID:
                return

            bot.answer_callback_query(call.id)

            parts = call.data.split("|")
            if len(parts) != 2:
                return

            user_id = int(parts[1])

            msg = bot.send_message(
                call.message.chat.id,
                f"✉️ Ответ пользователю {user_id}:"
            )
            bot.register_next_step_handler(msg, lambda m: send_reply(m, user_id))

        except Exception as e:
            print("REPLY ERROR:", e)

    # ===== SEND REPLY =====
    def send_reply(message, user_id: int):
        try:
            bot.send_message(
                user_id,
                f"💬 Ответ поддержки\n\n{message.text}"
            )
            bot.send_message(message.chat.id, "✅ Ответ отправлен")
        except Exception as e:
            print("SEND REPLY ERROR:", e)

    # ===== TOKEN =====
    @bot.callback_query_handler(func=lambda c: c.data == "token")
    def token(call):
        if not rate_limit(bot, call):
            return

        try:
            bot.answer_callback_query(call.id)
            user_id = call.from_user.id

            if not has_sub(user_id):
                bot.answer_callback_query(call.id, "❌ Нет подписки", show_alert=True)
                return

            sub = get_vpn_data(user_id)
            if not sub:
                bot.answer_callback_query(call.id, "❌ Не удалось получить данные VPN", show_alert=True)
                return

            safe_edit(bot, call, f"🔑 Твой VPN\n\n{sub}", back_button())

            qr = generate_qr(sub)
            bot.send_photo(call.message.chat.id, qr)

        except Exception as e:
            print("TOKEN ERROR:", e)

    # ===== SERVER STATUS =====
    @bot.callback_query_handler(func=lambda c: c.data == "server_status")
    def server_status(call):
        if not rate_limit(bot, call):
            return

        try:
            bot.answer_callback_query(call.id)

            lines = ["🖥 Статус серверов\n"]

            for server in SERVERS:
                name = server["name"]
                url = server["url"]

                try:
                    r = requests.get(url, verify=False, timeout=5)
                    status = "🟢 Онлайн"
                except requests.exceptions.Timeout:
                    status = "🔴 Таймаут"
                except Exception:
                    status = "🔴 Недоступен"

                lines.append(f"{name}\n{status}")

            safe_edit(bot, call, "\n\n".join(lines), back_button())

        except Exception as e:
            print("SERVER STATUS ERROR:", e)
