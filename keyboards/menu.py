from telebot import types
from config import ADMIN_ID

def main_menu():
    markup = types.InlineKeyboardMarkup()

    markup.row(
        types.InlineKeyboardButton("👤 Профиль", callback_data="profile")
    )

    markup.row(
        types.InlineKeyboardButton("💎 Купить VPN", callback_data="buy"),
        types.InlineKeyboardButton("🔑 Мой VPN", callback_data="token")
    )

    markup.row(
        types.InlineKeyboardButton("📊 Проверить подписку", callback_data="check_sub")
    )

    if

    return markup