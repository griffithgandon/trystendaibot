from telebot import types
from keyboards.menu import main_menu
from database.database import *
from services.vpn import create_or_update_user
from config import ADMIN_ID


def register_handlers(bot):

    # START
    @bot.message_handler(commands=['start'])
    def start(message):
        add_user(message.from_user.id)

        bot.send_message(
            message.chat.id,
            "TRYSTENDAI",
            reply_markup=main_menu()
        )

    # PROFILE
    @bot.callback_query_handler(func=lambda c: c.data == "profile")
    def profile(call):

        status = "✅ Активна" if has_sub(call.from_user.id) else "❌ Нет"

        bot.send_message(
            call.message.chat.id,
            f"""👤 Профиль\nID: {call.from_user.id}\nПодписка: {status}"""
        )

    # BUY
    @bot.callback_query_handler(func=lambda c: c.data == "buy")
    def buy(call):

        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "✅ Я оплатил",
                callback_data="paid"
            )
        )

        bot.send_message(
            call.message.chat.id,
            "Переведи 100₽ на карту XXXXX\nПосле оплаты нажми кнопку",
            reply_markup=markup
        )

    # USER CLICK PAID
    @bot.callback_query_handler(func=lambda c: c.data == "paid")
    def paid(call):

        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "✅ Подтвердить",
                callback_data=f"approve_{call.from_user.id}"
            )
        )
        for admin_id in ADMIN_ID:
            try:
                bot.send_message(
                    admin_id,  # ← ВАЖНО: именно admin_id
                    f"Оплата от {call.from_user.id}",
                    reply_markup=markup
                )
                print(f"Отправлено админу {admin_id}")
            except Exception as e:
                print(f"Не удалось отправить админу {admin_id}: {e}")   

    # ADMIN APPROVE
    @bot.callback_query_handler(func=lambda c: c.data.startswith("approve_"))
    def approve(call):

        user_id = int(call.data.split("_")[1])

        set_subscription(user_id, 30)

        vpn_id = create_or_update_user(user_id, 30)

        save_vpn_id(user_id, vpn_id)

        bot.send_message(user_id, "✅ Подписка активирована")

        bot.answer_callback_query(call.id, "Готово")

    # TOKEN
    @bot.callback_query_handler(func=lambda c: c.data == "token")
    def token(call):

        if not has_sub(call.from_user.id):
            bot.send_message(call.message.chat.id, "❌ Нет подписки")
            return

        vpn_id = get_vpn_id(call.from_user.id)

        link = f"vless://{vpn_id}@YOUR_IP:443"

        bot.send_message(
            call.message.chat.id,
            f"🔑 Ваш VPN:\n{link}"
        )

    # CHECK SUB
    @bot.callback_query_handler(func=lambda c: c.data == "check_sub")
    def check(call):

        if has_sub(call.from_user.id):
            bot.send_message(call.message.chat.id, "✅ Подписка активна")
        else:
            bot.send_message(call.message.chat.id, "❌ Подписки нет")

    @bot.message_handler(func=lambda m: True)
    def debug(message):
        print("USER ID:", message.from_user.id)
        print("CHAT ID:", message.chat.id)