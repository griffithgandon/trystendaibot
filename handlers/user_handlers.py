from telebot import types
from database.database import *
from services.vpn import create_user, get_vpn_data
from config import ADMIN_ID
from io import BytesIO
import qrcode


def register_handlers(bot):

    # ===== START =====
    @bot.message_handler(commands=['start'])
    def start(message):
        add_user(message.from_user.id)

        # если ник уже есть — не спрашиваем
        if get_username(message.from_user.id):
            send_main_menu(message)
            return

        bot.send_message(message.chat.id, "👤 Введи свой ник:")
        bot.register_next_step_handler(message, save_name)

    # ===== СОХРАНЕНИЕ НИКА =====
    def save_name(message):
        user_id = message.from_user.id
        username = message.text.strip()

        if not username:
            bot.send_message(message.chat.id, "❌ Ник не может быть пустым, попробуй ещё раз:")
            bot.register_next_step_handler(message, save_name)
            return

        save_username(user_id, username)

        bot.send_message(message.chat.id, f"✅ Ник сохранён: {username}")
        send_main_menu(message)

    # ===== ГЛАВНОЕ МЕНЮ =====
    def send_main_menu(message):
        markup = types.InlineKeyboardMarkup()

        markup.row(types.InlineKeyboardButton("👤 Профиль", callback_data="profile"))
        markup.row(
            types.InlineKeyboardButton("💎 Купить VPN", callback_data="buy"),
            types.InlineKeyboardButton("🔑 Мой VPN", callback_data="token")
        )
        markup.row(types.InlineKeyboardButton("📊 Проверить подписку", callback_data="check_sub"))

        if message.from_user.id in ADMIN_ID:
            markup.row(types.InlineKeyboardButton("⚙️ Админ меню", callback_data="admin_panel"))

        bot.send_message(message.chat.id, "Телеграм бот: Trystendai", reply_markup=markup)

    # ===== PROFILE =====
    @bot.callback_query_handler(func=lambda c: c.data == "profile")
    def profile(call):
        status = "✅ Активна" if has_sub(call.from_user.id) else "❌ Нет"
        username = get_username(call.from_user.id) or "не задан"

        bot.send_message(
            call.message.chat.id,
            f"👤 ID: {call.from_user.id}\n"
            f"Ник: {username}\n"
            f"Подписка: {status}"
        )

    # ===== BUY =====
    @bot.callback_query_handler(func=lambda c: c.data == "buy")
    def buy(call):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Я оплатил", callback_data="paid"))

        bot.send_message(call.message.chat.id, "Оплати и нажми кнопку", reply_markup=markup)

    # ===== PAID =====
    @bot.callback_query_handler(func=lambda c: c.data == "paid")
    def paid(call):
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "✅ Подтвердить",
                callback_data=f"approve_{call.from_user.id}"
            )
        )

        for admin in ADMIN_ID:
            bot.send_message(admin, f"Оплата от {call.from_user.id}", reply_markup=markup)

    # ===== APPROVE =====
    @bot.callback_query_handler(func=lambda c: c.data.startswith("approve_"))
    def approve(call):

        user_id = int(call.data.split("_")[1])
        days = 30

        set_subscription(user_id, days)
        create_user(user_id, days)

        bot.send_message(user_id, "✅ Подписка выдана")

    # ===== VPN =====
    @bot.callback_query_handler(func=lambda c: c.data == "token")
    def token(call):

        user_id = call.from_user.id

        if not has_sub(user_id):
            bot.send_message(call.message.chat.id, "❌ Нет подписки")
            return

        sub = get_vpn_data(user_id)

        if not sub:
            bot.send_message(call.message.chat.id, "❌ Подписка не найдена")
            return

        text = f"""🔑 Твои данные VPN:

📡 Подписка:
{sub}

📱 Добавь в:
Clash / V2Ray / Sing-box
"""

        bot.send_message(call.message.chat.id, text)

        # ===== QR (СТАБИЛЬНЫЙ) =====
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(sub)
        qr.make(fit=True)

        img = qr.make_image()

        bio = BytesIO()
        bio.name = "qr.png"
        img.save(bio, "PNG")
        bio.seek(0)

        bot.send_photo(
            call.message.chat.id,
            bio,
            caption="📡 QR подписки (все протоколы)"
        )

    # ===== CHECK SUB =====
    @bot.callback_query_handler(func=lambda c: c.data == "check_sub")
    def check(call):
        if has_sub(call.from_user.id):
            bot.send_message(call.message.chat.id, "✅ Подписка активна")
        else:
            bot.send_message(call.message.chat.id, "❌ Нет подписки")