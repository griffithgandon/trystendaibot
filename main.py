import telebot
from telebot import types

from config import TOKEN, ADMIN_ID, PRICE, SUB_DAYS
from database import *

bot = telebot.TeleBot(TOKEN)

broadcast_mode = False
support_mode = {}


# ========= USER MENU =========

def main_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💎 Подписка", callback_data="buy"))
    markup.add(types.InlineKeyboardButton("👤 Профиль", callback_data="profile"))
    markup.add(types.InlineKeyboardButton("🆘 Поддержка", callback_data="support"))
    return markup


# ========= ADMIN MENU =========

def admin_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📊 Статистика", callback_data="stats"))
    markup.add(types.InlineKeyboardButton("📢 Рассылка", callback_data="broadcast"))
    markup.add(types.InlineKeyboardButton("👥 Пользователи", callback_data="users"))
    return markup


# ========= START =========

@bot.message_handler(commands=['start'])
def start(message):
    add_user(message.from_user.id)

    bot.send_message(
        message.chat.id,
        "TRYSTENDAI BOT",
        reply_markup=main_menu()
    )


# ========= PROFILE =========

@bot.callback_query_handler(func=lambda c: c.data == "profile")
def profile(call):

    status = "✅ Активна" if has_sub(call.from_user.id) else "❌ Нет"

    bot.send_message(
        call.message.chat.id,
        f"""
👤 Профиль

ID: {call.from_user.id}
Подписка: {status}
"""
    )


# ========= BUY =========

@bot.callback_query_handler(func=lambda c: c.data == "buy")
def buy(call):

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Я оплатил", callback_data="paid"))

    bot.send_message(
        call.message.chat.id,
        f"""
💳 Оплата подписки

Цена: {PRICE}₽

Перевод:
2200 7000 1234 5678

Комментарий:
{call.from_user.id}
""",
        reply_markup=markup
    )


# ========= USER PAID =========

@bot.callback_query_handler(func=lambda c: c.data == "paid")
def paid(call):

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "✅ Подтвердить",
            callback_data=f"approve_{call.from_user.id}"
        )
    )

    bot.send_message(
        ADMIN_ID,
        f"💰 Оплата\nID: {call.from_user.id}",
        reply_markup=markup
    )

    bot.answer_callback_query(call.id, "Отправлено админу ✅")


# ========= APPROVE =========

@bot.callback_query_handler(func=lambda c: c.data.startswith("approve_"))
def approve(call):

    if call.from_user.id != ADMIN_ID:
        return

    user_id = int(call.data.split("_")[1])

    activate_sub(user_id, SUB_DAYS)

    bot.send_message(user_id, "✅ Подписка активирована!")

    bot.edit_message_text(
        "Оплата подтверждена ✅",
        call.message.chat.id,
        call.message.message_id
    )


# ========= VIP =========

@bot.message_handler(commands=['vip'])
def vip(message):

    if not has_sub(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Нет подписки")
        return

    bot.send_message(message.chat.id, "🔥 VIP доступ открыт")


# ========= ADMIN =========

@bot.message_handler(commands=['admin'])
def admin(message):

    if message.from_user.id != ADMIN_ID:
        return

    bot.send_message(
        message.chat.id,
        "👑 Админ панель",
        reply_markup=admin_menu()
    )


# ========= STATS =========

@bot.callback_query_handler(func=lambda c: c.data == "stats")
def stats(call):

    if call.from_user.id != ADMIN_ID:
        return

    users_count, payments = get_stats()

    bot.send_message(
        call.message.chat.id,
        f"""
📊 Статистика

Пользователей: {users_count}
Продаж: {payments}
Доход: {payments * PRICE}₽
"""
    )


# ========= USERS LIST =========

@bot.callback_query_handler(func=lambda c: c.data == "users")
def users_list_handler(call):

    if call.from_user.id != ADMIN_ID:
        return

    users_list = get_users()

    text = "👥 Пользователи:\n\n"

    for user in users_list[:30]:
        text += f"{user[0]}\n"

    bot.send_message(call.message.chat.id, text)


# ========= BROADCAST =========

@bot.callback_query_handler(func=lambda c: c.data == "broadcast")
def broadcast(call):

    global broadcast_mode

    if call.from_user.id != ADMIN_ID:
        return

    broadcast_mode = True

    bot.send_message(call.message.chat.id, "✉️ Отправь текст рассылки")


# ========= SEND BROADCAST =========

@bot.message_handler(func=lambda message: broadcast_mode)
def send_broadcast(message):

    global broadcast_mode

    if message.from_user.id != ADMIN_ID:
        return

    users_list = get_users()

    sent = 0

    for user in users_list:
        try:
            bot.send_message(user[0], message.text)
            sent += 1
        except Exception as e:
            print(f"Ошибка при отправке {user[0]}: {e}")

    broadcast_mode = False

    bot.send_message(
        message.chat.id,
        f"✅ Рассылка завершена\nОтправлено: {sent}"
    )


# ========= SUPPORT =========

@bot.callback_query_handler(func=lambda c: c.data == "support")
def support(call):

    support_mode[call.from_user.id] = True

    bot.send_message(
        call.message.chat.id,
        "✉️ Напиши сообщение в поддержку"
    )


@bot.message_handler(func=lambda message: support_mode.get(message.from_user.id))
def handle_support_message(message):

    support_mode.pop(message.from_user.id, None)

    bot.send_message(
        ADMIN_ID,
        f"""
🆘 Новое сообщение в поддержку

ID: {message.from_user.id}
Сообщение:
{message.text}
"""
    )

    bot.send_message(
        message.chat.id,
        "✅ Сообщение отправлено в поддержку"
    )


@bot.message_handler(func=lambda message: message.reply_to_message and message.from_user.id == ADMIN_ID)
def reply_to_user(message):

    try:
        text = message.reply_to_message.text
        user_id = int(text.split("ID: ")[1].split("\n")[0])

        bot.send_message(
            user_id,
            f"💬 Ответ поддержки:\n\n{message.text}"
        )

    except Exception as e:
        print("Ошибка ответа:", e)


print("TRYSTENDAI BOT STARTED")
bot.infinity_polling()