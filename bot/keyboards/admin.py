from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")
    )
    builder.row(InlineKeyboardButton(text="🟢 Онлайн", callback_data="admin_online"))
    builder.row(InlineKeyboardButton(text="💰 Заявки", callback_data="pending_list"))
    builder.row(
        InlineKeyboardButton(text="🎁 Пробные периоды", callback_data="trial_list")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")
    )
    builder.row(
        InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="menu"))
    return builder.as_markup()


def back_to_admin() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="admin_panel")
    return builder.as_markup()


def user_actions(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Выдать", callback_data=f"give_{user_id}"),
        InlineKeyboardButton(text="⏸ Отключить", callback_data=f"remove_{user_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_{user_id}"),
        InlineKeyboardButton(text="♻️ Пересоздать", callback_data=f"recreate_{user_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="▶️ Включить", callback_data=f"enable_{user_id}")
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_users"))
    return builder.as_markup()


def approve_payment(user_id: int, tariff_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=f"approve|{user_id}|{tariff_id}",
        )
    )
    return builder.as_markup()


def approve_trial(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Одобрить",
            callback_data=f"approve_trial|{user_id}",
        ),
        InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=f"decline_trial|{user_id}",
        ),
    )
    return builder.as_markup()


def reply_to_user(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✉️ Ответить", callback_data=f"reply|{user_id}")
    return builder.as_markup()


def users_list(rows: list) -> InlineKeyboardMarkup:
    """Список пользователей для админ-панели."""
    builder = InlineKeyboardBuilder()

    for row in rows:
        uid = row["user_id"]
        builder.row(
            InlineKeyboardButton(
                text=f"👤 {uid}",
                callback_data=f"user_{uid}",
            )
        )

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel"))
    return builder.as_markup()