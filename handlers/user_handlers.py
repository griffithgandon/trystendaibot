from telebot import types
from config import ADMIN_ID
from database.db import *
from services.vpn import create_user, get_vpn_data
from utils.qr import generate_qr


# ===== UI =====
def get_main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)

    markup.add(
        types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        types.InlineKeyboardButton("💎 Купить VPN", callback_data="buy"),
        types.InlineKeyboardButton("🔑 Мой VPN", callback_data="token"),
        types.InlineKeyboardButton("📊 Подписка", callback_data="check_sub")
    )

    if user_id in ADMIN_ID:
        markup.add(
            types.InlineKeyboardButton("⚙️ Админ", callback_data="admin_panel")
        )

    return markup


def back_button():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu"))
    return markup


# ===== SAFE EDIT (фикс ошибки 400) =====
def safe_edit(bot, call, text, markup):
    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
    except:
        # если текст тот же — просто игнорим
        pass


# ===== HANDLERS =====
def register_handlers(bot):

    # ===== START =====
    @bot.message_handler(commands=['start'])
    def start(message):
        user_id = message.from_user.id

        add_user(user_id)

        if get_username(user_id):
            bot.send_message(
                message.chat.id,
                "📱 Главное меню:",
                reply_markup=get_main_menu(user_id)
            )
        else:
            msg = bot.send_message(message.chat.id, "👋 Введи свой ник:")
            bot.register_next_step_handler(msg, save_name)


    # ===== SAVE USERNAME =====
    def save_name(message):
        user_id = message.from_user.id
        username = message.text.strip()

        if len(username) < 2:
            msg = bot.send_message(message.chat.id, "❌ Ник слишком короткий, попробуй ещё:")
            bot.register_next_step_handler(msg, save_name)
            return

        save_username(user_id, username)

        bot.send_message(
            message.chat.id,
            f"✅ Ник сохранён: {username}",
            reply_markup=get_main_menu(user_id)
        )


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
        bot.answer_callback_query(call.id)

        user_id = call.from_user.id
        username = get_username(user_id) or "—"
        status = "✅ Активна" if has_sub(user_id) else "❌ Нет"

        text = f"""👤 Профиль

ID: {user_id}
Ник: {username}
Подписка: {status}
"""

        safe_edit(bot, call, text, back_button())


    # ===== BUY =====
    @bot.callback_query_handler(func=lambda c: c.data == "buy")
    def buy(call):
        bot.answer_callback_query(call.id)

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Я оплатил", callback_data="paid"))
        markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu"))

        safe_edit(
            bot,
            call,
            "💎 Оплати VPN и нажми кнопку ниже",
            markup
        )


    # ===== PAID =====
    @bot.callback_query_handler(func=lambda c: c.data == "paid")
    def paid(call):
        bot.answer_callback_query(call.id)

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "✅ Подтвердить",
                callback_data=f"approve_{call.from_user.id}"
            )
        )

        for admin in ADMIN_ID:
            bot.send_message(admin, f"💰 Оплата от {call.from_user.id}", reply_markup=markup)


    # ===== APPROVE =====
    @bot.callback_query_handler(func=lambda c: c.data.startswith("approve_"))
    def approve(call):
        bot.answer_callback_query(call.id)

        user_id = int(call.data.split("_")[1])

        set_subscription(user_id, 30)
        create_user(user_id, 30)

        bot.send_message(user_id, "✅ Подписка выдана")


    # ===== VPN =====
    @bot.callback_query_handler(func=lambda c: c.data == "token")
    def token(call):
        bot.answer_callback_query(call.id)

        user_id = call.from_user.id

        if not has_sub(user_id):
            bot.answer_callback_query(call.id, "❌ Нет подписки")
            return

        sub = get_vpn_data(user_id)

        if not sub:
            bot.answer_callback_query(call.id, "❌ Подписка не найдена")
            return

        text = f"""🔑 Твой VPN

{sub}
"""

        safe_edit(bot, call, text, back_button())

        # QR (один раз, без спама)
        try:
            qr = generate_qr(sub)
            bot.send_photo(call.message.chat.id, qr)
        except Exception as e:
            print("QR ERROR:", e)


    # ===== CHECK =====
    @bot.callback_query_handler(func=lambda c: c.data == "check_sub")
    def check(call):
        bot.answer_callback_query(call.id)

        text = "✅ Подписка активна" if has_sub(call.from_user.id) else "❌ Нет подписки"

        safe_edit(bot, call, text, back_button())