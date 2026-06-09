"""
Админские хендлеры (роутер admin).

Порт с telebot handlers/admin_handlers.py:
  - доступ ограничен фильтром IsAdmin на весь роутер (вместо is_admin() в каждом)
  - register_next_step_handler (рассылка) -> AdminStates.waiting_for_broadcast
  - safe_edit переиспользуется из user-роутера
"""

import asyncio
import logging
import time

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message, TelegramObject
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import get_settings
from bot.database.repo import (
    get_all_user_ids,
    get_pending_payments,
    get_pending_trials,
    get_recent_users,
    get_sub_until,
    get_telegram_username,
    get_total_subs,
    get_total_trials,
    get_total_users,
    get_username,
    has_pending_payment,
    has_sub,
    has_used_trial,
    is_sub_disabled,
    remove_pending_payment,
    remove_sub,
    set_sub_disabled,
    set_subscription,
    set_trial_used,
)
from bot.handlers.user import safe_edit
from bot.keyboards.admin import admin_menu, back_to_admin, user_actions
from bot.services.vpn import (
    create_user,
    delete_user,
    disable_user,
    enable_user,
    extend_user,
    get_online_users,
)
from bot.states import AdminStates

settings = get_settings()
logger = logging.getLogger(__name__)


# ===== Доступ только админам (фильтр на весь роутер) =====

class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject) -> bool:
        user = getattr(event, "from_user", None)
        return user is not None and user.id in settings.admin_ids


router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def _parse_id(data: str | None, prefix: str) -> int | None:
    try:
        return int((data or "")[len(prefix):])
    except ValueError:
        return None


# ===== ADMIN PANEL =====

@router.callback_query(F.data == "admin_panel")
async def admin_panel(call: CallbackQuery) -> None:
    await call.answer()
    await safe_edit(call, "⚙️ Админ панель", admin_menu())


# ===== USERS LIST =====

@router.callback_query(F.data == "admin_users")
async def users(call: CallbackQuery) -> None:
    await call.answer()

    rows = await get_recent_users(20)
    builder = InlineKeyboardBuilder()
    for row in rows:
        uid = row["user_id"]
        username = await get_username(uid) or "Без ника"
        builder.row(
            InlineKeyboardButton(
                text=f"👤 {username} | {uid}", callback_data=f"user_{uid}"
            )
        )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel"))
    await safe_edit(call, "👥 Последние пользователи:", builder.as_markup())


# ===== USER MENU =====

@router.callback_query(F.data.startswith("user_"))
async def user_menu(call: CallbackQuery) -> None:
    await call.answer()
    user_id = _parse_id(call.data, "user_")
    if user_id is None:
        return

    username = await get_username(user_id) or "Без ника"
    tg_username = await get_telegram_username(user_id) or "нет"
    sub_until = await get_sub_until(user_id)
    trial_status = (
        "✅ Использован" if await has_used_trial(user_id) else "🎁 Не использован"
    )

    if sub_until > int(time.time()):
        sub_text = time.strftime("%d.%m.%Y %H:%M", time.localtime(sub_until))
    elif await is_sub_disabled(user_id):
        sub_text = "⏸ Отключена"
    else:
        sub_text = "Нет подписки"

    await safe_edit(
        call,
        f"👤 Пользователь\n\n"
        f"🪪 Ник: {username}\n"
        f"🌐 Telegram: @{tg_username}\n"
        f"🆔 ID: {user_id}\n\n"
        f"💎 Подписка:\n{sub_text}\n\n"
        f"🎁 Пробный период: {trial_status}",
        user_actions(user_id),
    )


# ===== GIVE (выдать 30 дней) =====

@router.callback_query(F.data.startswith("give_"))
async def give(call: CallbackQuery, bot: Bot) -> None:
    await call.answer()
    user_id = _parse_id(call.data, "give_")
    if user_id is None:
        return

    try:
        already_active = await has_sub(user_id)
        await set_subscription(user_id, 30)
        if already_active:
            await extend_user(user_id, 30)
        else:
            await create_user(user_id, 30)

        await safe_edit(call, f"✅ Выдано {user_id}", back_to_admin())
        await _try_send(bot, user_id, "✅ Подписка выдана")
    except Exception as e:
        logger.error("GIVE ERROR: %s", e)


# ===== REMOVE (отключить, конфиг остаётся) =====

@router.callback_query(F.data.startswith("remove_"))
async def remove(call: CallbackQuery, bot: Bot) -> None:
    await call.answer()
    user_id = _parse_id(call.data, "remove_")
    if user_id is None:
        return

    try:
        await disable_user(user_id)
        await remove_sub(user_id)
        await set_sub_disabled(user_id, True)
        await safe_edit(call, f"⏸ Подписка {user_id} отключена", back_to_admin())
        await _try_send(bot, user_id, "⏸ Ваша подписка отключена")
    except Exception as e:
        logger.error("DISABLE ERROR: %s", e)


# ===== ENABLE (включить отключённого) =====

@router.callback_query(F.data.startswith("enable_"))
async def enable(call: CallbackQuery, bot: Bot) -> None:
    await call.answer()
    user_id = _parse_id(call.data, "enable_")
    if user_id is None:
        return

    try:
        await enable_user(user_id)
        await set_subscription(user_id, 30)
        await set_sub_disabled(user_id, False)
        await safe_edit(
            call, f"▶️ Пользователь {user_id} включён (+30 дней)", back_to_admin()
        )
        await _try_send(bot, user_id, "▶️ Ваша подписка включена")
    except Exception as e:
        logger.error("ENABLE ERROR: %s", e)


# ===== DELETE (полное удаление с панели) =====

@router.callback_query(F.data.startswith("delete_"))
async def delete(call: CallbackQuery, bot: Bot) -> None:
    await call.answer()
    user_id = _parse_id(call.data, "delete_")
    if user_id is None:
        return

    try:
        await delete_user(user_id)
        await remove_sub(user_id)
        await safe_edit(
            call, f"🗑 Пользователь {user_id} удалён с панели", back_to_admin()
        )
        await _try_send(bot, user_id, "❌ Ваша подписка удалена")
    except Exception as e:
        logger.error("DELETE ERROR: %s", e)


# ===== RECREATE =====

@router.callback_query(F.data.startswith("recreate_"))
async def recreate(call: CallbackQuery, bot: Bot) -> None:
    await call.answer()
    user_id = _parse_id(call.data, "recreate_")
    if user_id is None:
        return

    try:
        await delete_user(user_id)  # полное удаление перед пересозданием
        await set_subscription(user_id, 30)
        await create_user(user_id, 30)
        await safe_edit(call, f"♻️ Пересоздан {user_id}", back_to_admin())
        await _try_send(bot, user_id, "♻️ VPN пересоздан")
    except Exception as e:
        logger.error("RECREATE ERROR: %s", e)


# ===== STATS =====

@router.callback_query(F.data == "admin_stats")
async def stats(call: CallbackQuery) -> None:
    await call.answer()
    total = await get_total_users()
    active = await get_total_subs()
    trials = await get_total_trials()

    await safe_edit(
        call,
        f"📊 Статистика\n\n"
        f"👥 Всего пользователей: {total}\n"
        f"💎 Активных подписок: {active}\n"
        f"🎁 Использовали пробный: {trials}",
        back_to_admin(),
    )


# ===== ONLINE =====

@router.callback_query(F.data == "admin_online")
async def online(call: CallbackQuery) -> None:
    await call.answer()
    clients = await get_online_users()

    if clients is None:
        await safe_edit(call, "❌ Не удалось получить данные с панели", back_to_admin())
        return
    if not clients:
        await safe_edit(call, "🟡 Сейчас никого нет онлайн", back_to_admin())
        return

    seen: set[str] = set()
    lines: list[str] = []
    now = int(time.time())

    for email in clients:
        uid_str = email.split("_")[0]
        if uid_str in seen:
            continue
        seen.add(uid_str)

        try:
            uid = int(uid_str)
        except ValueError:
            lines.append(f"• {email}")
            continue

        username = await get_username(uid) or "Без ника"
        tg = await get_telegram_username(uid) or "—"
        sub_until = await get_sub_until(uid)

        if sub_until > now:
            days_left = (sub_until - now) // 86400
            hours_left = ((sub_until - now) % 86400) // 3600
            expire_date = time.strftime("%d.%m.%Y", time.localtime(sub_until))
            remain = (
                f"{days_left}д {hours_left}ч" if days_left > 0 else f"{hours_left}ч"
            )
            sub_info = f"до {expire_date} (осталось {remain})"
        else:
            sub_info = "⚠️ истекла"

        lines.append(f"• {username} | @{tg} | {uid}\n  💎 {sub_info}")

    text = f"🟢 Онлайн сейчас: {len(seen)}\n\n" + "\n\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n…"

    await safe_edit(call, text, back_to_admin())


# ===== PENDING PAYMENTS =====

@router.callback_query(F.data == "pending_list")
async def pending_list(call: CallbackQuery) -> None:
    await call.answer()
    payments = await get_pending_payments()

    if not payments:
        await safe_edit(call, "❌ Активных заявок нет", back_to_admin())
        return

    builder = InlineKeyboardBuilder()
    text = "💰 Активные заявки\n"

    for row in payments:
        user_id = row["user_id"]
        payment_type = row["payment_type"]
        username = await get_username(user_id) or "Без ника"
        type_label = "🔄 Продление" if payment_type == "renew" else "🆕 Новая"
        text += f"\n{type_label}\n👤 {username}\n🆔 ID: {user_id}\n"
        builder.row(
            InlineKeyboardButton(
                text=f"{type_label} | {user_id}", callback_data=f"user_{user_id}"
            )
        )

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel"))
    await safe_edit(call, text, builder.as_markup())


# ===== TRIAL LIST =====

@router.callback_query(F.data == "trial_list")
async def trial_list(call: CallbackQuery) -> None:
    await call.answer()
    trials = await get_pending_trials()

    if not trials:
        await safe_edit(call, "🎁 Заявок на пробный период нет", back_to_admin())
        return

    builder = InlineKeyboardBuilder()
    text = f"🎁 Заявки на пробный период ({settings.trial_days} дней)\n"

    for row in trials:
        user_id = row["user_id"]
        created_at = row["created_at"]
        username = await get_username(user_id) or "Без ника"
        tg = await get_telegram_username(user_id) or "—"
        dt = time.strftime("%d.%m %H:%M", time.localtime(created_at))
        text += f"\n👤 {username} | @{tg}\n🆔 ID: {user_id} | 🕐 {dt}\n"
        builder.row(
            InlineKeyboardButton(
                text=f"✅ {username} ({user_id})",
                callback_data=f"approve_trial|{user_id}",
            ),
            InlineKeyboardButton(
                text="❌", callback_data=f"decline_trial|{user_id}"
            ),
        )

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel"))
    await safe_edit(call, text, builder.as_markup())


# ===== APPROVE TRIAL =====

@router.callback_query(F.data.startswith("approve_trial|"))
async def approve_trial(call: CallbackQuery, bot: Bot) -> None:
    parts = (call.data or "").split("|")
    if len(parts) != 2:
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        return

    if not await has_pending_payment(user_id):
        await call.answer("⚠️ Заявка не найдена или уже обработана", show_alert=True)
        return

    if await has_used_trial(user_id):
        await call.answer(
            "⚠️ Пользователь уже использовал пробный период", show_alert=True
        )
        await remove_pending_payment(user_id)
        return

    try:
        await set_subscription(user_id, settings.trial_days)
        await set_trial_used(user_id)
        await create_user(user_id, settings.trial_days)
        await remove_pending_payment(user_id)

        await _try_send(
            bot,
            user_id,
            f"🎁 Пробный период активирован!\n\n"
            f"📅 Длительность: {settings.trial_days} дней\n\n"
            f"Нажми 🔑 Мой VPN чтобы получить конфиг.",
        )
        await call.answer("✅ Пробный период выдан")
        await safe_edit(
            call, f"✅ Пробный период выдан пользователю {user_id}", back_to_admin()
        )
    except Exception as e:
        logger.error("APPROVE TRIAL ERROR: %s", e)
        await call.answer("❌ Ошибка при выдаче", show_alert=True)


# ===== DECLINE TRIAL =====

@router.callback_query(F.data.startswith("decline_trial|"))
async def decline_trial(call: CallbackQuery, bot: Bot) -> None:
    parts = (call.data or "").split("|")
    if len(parts) != 2:
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        return

    try:
        await remove_pending_payment(user_id)
        await _try_send(
            bot,
            user_id,
            "❌ Заявка на пробный период отклонена.\n\n"
            "Вы можете приобрести подписку в разделе 💎 Купить VPN.",
        )
        await call.answer("❌ Заявка отклонена")
        await safe_edit(
            call, f"❌ Заявка пользователя {user_id} отклонена", back_to_admin()
        )
    except Exception as e:
        logger.error("DECLINE TRIAL ERROR: %s", e)
        await call.answer("❌ Ошибка", show_alert=True)


# ===== BROADCAST =====

@router.callback_query(F.data == "admin_broadcast")
async def broadcast(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await safe_edit(call, "✍️ Введи текст рассылки", back_to_admin())
    await state.set_state(AdminStates.waiting_for_broadcast)


@router.message(AdminStates.waiting_for_broadcast)
async def send_broadcast(message: Message, state: FSMContext, bot: Bot) -> None:
    text = message.text
    if not text:
        await message.answer("❌ Пустой текст рассылки, попробуй ещё раз")
        return  # остаёмся в состоянии

    await state.clear()
    user_ids = await get_all_user_ids()
    sent = 0
    failed = 0

    for uid in user_ids:
        try:
            await bot.send_message(uid, text)
            sent += 1
            await asyncio.sleep(0.05)  # не упираться в лимиты Telegram
        except Exception:
            failed += 1

    await message.answer(f"✅ Отправлено: {sent}\n❌ Не доставлено: {failed}")


# ===== Помощник =====

async def _try_send(bot: Bot, user_id: int, text: str) -> None:
    try:
        await bot.send_message(user_id, text)
    except Exception:
        pass
