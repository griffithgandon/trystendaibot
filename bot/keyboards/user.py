from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import get_settings

settings = get_settings()


def main_menu(user_id: int, has_sub: bool, sub_disabled: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
        InlineKeyboardButton(text="💎 Купить VPN", callback_data="buy"),
    )
    builder.row(
        InlineKeyboardButton(text="🔑 Мой VPN", callback_data="token"),
        InlineKeyboardButton(text="💬 Поддержка", callback_data="support"),
    )

    if has_sub or sub_disabled:
        builder.row(
            InlineKeyboardButton(text="🔄 Продлить", callback_data="renew")
        )

    builder.row(
        InlineKeyboardButton(text="🖥 Статус сервера", callback_data="server_status")
    )

    if user_id in settings.admin_ids:
        builder.row(
            InlineKeyboardButton(text="⚙️ Админ", callback_data="admin_panel")
        )

    return builder.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="menu")
    return builder.as_markup()


def buy_menu(has_trial: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if has_trial:
        builder.row(
            InlineKeyboardButton(
                text=f"🎁 Пробный период — {settings.trial_days} дней бесплатно",
                callback_data="trial_request",
            )
        )

    for tariff_id, tariff in settings.tariffs.items():
        builder.row(
            InlineKeyboardButton(
                text=tariff["title"],
                callback_data=f"tariff_{tariff_id}",
            )
        )

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="menu"))
    return builder.as_markup()


def tariff_payment(tariff_id: str, back_to: str = "buy") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"paid_{tariff_id}")
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_to))
    return builder.as_markup()


def renew_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for tariff_id, tariff in settings.tariffs.items():
        builder.row(
            InlineKeyboardButton(
                text=tariff["title"],
                callback_data=f"renew_tariff_{tariff_id}",
            )
        )

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="menu"))
    return builder.as_markup()


def renew_payment(tariff_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Я оплатил",
            callback_data=f"renew_paid_{tariff_id}",
        )
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="renew"))
    return builder.as_markup()