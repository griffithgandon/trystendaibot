from telebot import types
from database.database import *
from services.vpn import create_user, get_vpn_data
from config import ADMIN_ID
import qrcode


def register_handlers(bot):
    @bot.message_handler(commands=['start'])
    def start(message):
        add_user(message.from_user.id)
        markup = types.InlineKeyboardMarkup()

        markup.row(types.InlineKeyboardButton("👤 Профиль", callback_data="profile"))

        markup.row(types.InlineKeyboardButton("💎 Купить VPN", callback_data="buy"),
                   types.InlineKeyboardButton("🔑 Мой VPN", callback_data="token"))

        markup.row(types.InlineKeyboardButton("📊 Проверить подписку", callback_data="check_sub"))

        bot.send_message(message.chat.id, "TRYSTENDAI BOT", reply_markup=markup)

    @bot.callback_query_handler(func=lambda c: c.data == "profile")
    def profile(call):
        status = "✅ Активна" if has_sub(call.from_user.id) else "❌ Нет"

        bot.send_message(
            call.message.chat.id,
            f"👤 ID: {call.from_user.id}\nПодписка: {status}"
        )

    @bot.callback_query_handler(func=lambda c: c.data == "buy")
    def buy(call):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Я оплатил", callback_data="paid"))

        bot.send_message(call.message.chat.id, "Оплати и нажми кнопку", reply_markup=markup)

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

        if not has_sub(call.from_user.id):
            bot.send_message(call.message.chat.id, "❌ Нет подписки")
            return

        data = get_vpn_data(call.from_user.id)

        if not data:
            bot.send_message(call.message.chat.id, "❌ VPN не найден")
            return

        text = f"🔑 Твои данные VPN:\n\nVLESS:\n{data['vless']}"

        if data["subscription"]:
            text += f"\n\n📡 Subscription:\n{data['subscription']}"
        else:
            text += "\n\n⚠️ Подписка не найдена"

        bot.send_message(call.message.chat.id, text)

        # 🔥 QR = ПОДПИСКА
        if data["subscription"]:
            qr = qrcode.make(data["subscription"])
            qr.save("sub_qr.png")

            with open("sub_qr.png", "rb") as f:
                bot.send_photo(
                    call.message.chat.id,
                    f,
                    caption="📡 QR подписки (все протоколы)"
                )

    @bot.callback_query_handler(func=lambda c: c.data == "check_sub")
    def check(call):
        if has_sub(call.from_user.id):
            bot.send_message(call.message.chat.id, "✅ Активна")
        else:
            bot.send_message(call.message.chat.id, "❌ Нет")