"""
Пользовательские хендлеры (роутер user).

Порт с telebot handlers/user_handlers.py:
  - register_next_step_handler -> FSM (UserStates / AdminStates)
  - rate_limit(...) -> ThrottlingMiddleware (глобально) + check_rate_limit (точечно)
  - safe_edit сохранён как помощник
"""

import logging
import time

import aiohttp
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import get_settings
from bot.database.repo import (
    add_pending_payment,
    add_user,
    get_pending_payment_info,
    get_sub_until,
    get_username,
    has_pending_payment,
    has_sub,
    has_used_trial,
    is_sub_disabled,
    remove_pending_payment,
    save_username,
    set_sub_disabled,
    set_subscription,
    set_trial_used,
)
from bot.keyboards.admin import approve_payment, approve_trial, reply_to_user
from bot.keyboards.user import (
    back_to_menu,
    buy_menu,
    main_menu,
    renew_menu,
    renew_payment,
    tariff_payment,
)
from bot.middlewares.throttling import (
    check_rate_limit,
    payment_limiter,
    start_limiter,
    support_limiter,
)
from bot.services.vpn import create_user, extend_user, get_vpn_data
from bot.states import AdminStates, UserStates
from bot.utils.qr import generate_qr

router = Router(name="user")
settings = get_settings()
logger = logging.getLogger(__name__)


# ===== Помощники =====

async def safe_edit(call: CallbackQuery, text: str, markup=None) -> None:
    """Редактирует сообщение, игнорируя 'message is not modified'."""
    msg = call.message
    if not isinstance(msg, Message):
        return
    try:
        await msg.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.error("SAFE EDIT ERROR: %s", e)


async def _notify_admins(bot: Bot, text: str, markup=None) -> None:
    for admin in settings.admin_ids:
        try:
            await bot.send_message(admin, text, reply_markup=markup)
        except Exception:
            pass


# ===== START =====

@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    if not await check_rate_limit(message, start_limiter):
        return

    user_id = message.from_user.id
    await add_user(user_id, message.from_user.username)

    if await get_username(user_id):
        await message.answer(
            "📱 Главное меню:",
            reply_markup=main_menu(
                user_id, await has_sub(user_id), await is_sub_disabled(user_id)
            ),
        )
    else:
        await message.answer("👋 Введи свой ник:")
        await state.set_state(UserStates.waiting_for_name)


# ===== SAVE NAME =====

@router.message(UserStates.waiting_for_name)
async def save_name(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    user_id = message.from_user.id
    username = (message.text or "").strip()

    if len(username) < 2 or len(username) > 32:
        await message.answer("❌ Ник должен быть от 2 до 32 символов")
        return  # остаёмся в состоянии waiting_for_name

    await save_username(user_id, username)
    await state.clear()
    await message.answer(
        f"✅ Ник сохранён: {username}",
        reply_markup=main_menu(
            user_id, await has_sub(user_id), await is_sub_disabled(user_id)
        ),
    )


# ===== MENU =====

@router.callback_query(F.data == "menu")
async def menu(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()  # выходим из любого незавершённого FSM-флоу
    await call.answer()
    await safe_edit(
        call,
        "📱 Главное меню:",
        main_menu(
            call.from_user.id,
            await has_sub(call.from_user.id),
            await is_sub_disabled(call.from_user.id),
        ),
    )


# ===== PROFILE =====

@router.callback_query(F.data == "profile")
async def profile(call: CallbackQuery) -> None:
    await call.answer()
    user_id = call.from_user.id
    username = await get_username(user_id) or "—"
    sub_until = await get_sub_until(user_id)
    trial_status = "✅ Использован" if await has_used_trial(user_id) else "🎁 Доступен"

    if sub_until > int(time.time()):
        date = time.strftime("%d.%m.%Y %H:%M", time.localtime(sub_until))
        status = f"✅ До {date}"
    elif await is_sub_disabled(user_id):
        status = "⏸ Отключена — продлите для восстановления"
    else:
        status = "❌ Нет"

    await safe_edit(
        call,
        f"👤 Профиль\n\n"
        f"🆔 ID: {user_id}\n"
        f"👤 Ник: {username}\n"
        f"💎 Подписка: {status}\n"
        f"🎁 Пробный период: {trial_status}",
        back_to_menu(),
    )


# ===== BUY =====

@router.callback_query(F.data == "buy")
async def buy(call: CallbackQuery) -> None:
    await call.answer()
    user_id = call.from_user.id

    if await has_sub(user_id):
        sub_until = await get_sub_until(user_id)
        date = time.strftime("%d.%m.%Y", time.localtime(sub_until))
        await call.answer(
            f"✅ У вас уже есть активная подписка до {date}\n\n"
            "Для продления используйте кнопку 🔄 Продлить",
            show_alert=True,
        )
        return

    has_trial = not await has_used_trial(user_id)
    await safe_edit(call, "💎 Выбери тариф:", buy_menu(has_trial))


# ===== TRIAL REQUEST =====

@router.callback_query(F.data == "trial_request")
async def trial_request(call: CallbackQuery, bot: Bot) -> None:
    if not await check_rate_limit(call, payment_limiter):
        return

    user_id = call.from_user.id

    if await has_used_trial(user_id):
        await call.answer("❌ Пробный период уже был использован", show_alert=True)
        return
    if await has_sub(user_id):
        await call.answer("❌ У вас уже есть активная подписка", show_alert=True)
        return
    if await has_pending_payment(user_id):
        await call.answer("⏳ У тебя уже есть активная заявка", show_alert=True)
        return

    await call.answer()
    username = await get_username(user_id) or "Без ника"

    # ── Авто-выдача ──
    if settings.trial_auto_approve:
        await set_subscription(user_id, settings.trial_days)
        await set_trial_used(user_id)
        await create_user(user_id, settings.trial_days)

        await safe_edit(
            call,
            f"🎁 Пробный период активирован!\n\n"
            f"📅 Длительность: {settings.trial_days} дней\n\n"
            f"Нажми 🔑 Мой VPN чтобы получить конфиг.",
            back_to_menu(),
        )
        await _notify_admins(
            bot,
            f"🎁 Пробный период выдан автоматически\n\n"
            f"👤 {username}\n🆔 ID: {user_id}\n📅 Дней: {settings.trial_days}",
        )
        return

    # ── Ручное подтверждение ──
    await add_pending_payment(user_id, "trial", payment_type="trial")
    await _notify_admins(
        bot,
        f"🎁 Заявка на пробный период\n\n"
        f"👤 {username}\n🆔 ID: {user_id}\n📅 Дней: {settings.trial_days}",
        approve_trial(user_id),
    )
    await safe_edit(
        call,
        "🎁 Заявка на пробный период отправлена\n\n"
        "⏳ Ожидайте подтверждения от администратора",
        back_to_menu(),
    )


# ===== RENEW =====

@router.callback_query(F.data == "renew")
async def renew(call: CallbackQuery) -> None:
    await call.answer()
    user_id = call.from_user.id

    if not await has_sub(user_id) and not await is_sub_disabled(user_id):
        await call.answer("❌ Нет активной подписки", show_alert=True)
        return

    await safe_edit(call, "🔄 Продление подписки\n\nВыбери тариф:", renew_menu())


# ===== RENEW TARIFF =====

@router.callback_query(F.data.startswith("renew_tariff_"))
async def renew_tariff(call: CallbackQuery) -> None:
    await call.answer()
    tariff_id = (call.data or "")[len("renew_tariff_"):]
    tariff = settings.tariffs.get(tariff_id)
    if not tariff:
        return

    sub_until = await get_sub_until(call.from_user.id)
    date = time.strftime("%d.%m.%Y", time.localtime(sub_until))

    text = (
        f"{settings.payment_text}\n\n"
        f"🔄 Продление подписки\n"
        f"📅 Текущая подписка до: {date}\n\n"
        f"📦 Тариф: {tariff['title']}\n"
        f"💰 Цена: {tariff['price']}₽\n"
        f"📅 Добавится: {tariff['days']} дней\n\n"
        f"🆔 Ваш ID:\n{call.from_user.id}"
    )
    await safe_edit(call, text, renew_payment(tariff_id))


# ===== RENEW PAID =====

@router.callback_query(F.data.startswith("renew_paid_"))
async def renew_paid(call: CallbackQuery, bot: Bot) -> None:
    if not await check_rate_limit(call, payment_limiter):
        return

    tariff_id = (call.data or "")[len("renew_paid_"):]
    tariff = settings.tariffs.get(tariff_id)
    if not tariff:
        return

    user_id = call.from_user.id
    if await has_pending_payment(user_id):
        await call.answer("⏳ У тебя уже есть активная заявка", show_alert=True)
        return

    await call.answer()
    await add_pending_payment(user_id, tariff_id, payment_type="renew")

    username = await get_username(user_id) or "Без ника"
    sub_until = await get_sub_until(user_id)
    date = time.strftime("%d.%m.%Y", time.localtime(sub_until))

    await _notify_admins(
        bot,
        f"🔄 Заявка на продление\n\n"
        f"👤 {username}\n🆔 ID: {user_id}\n📅 Подписка до: {date}\n\n"
        f"📦 Тариф: {tariff['title']}\n💰 Сумма: {tariff['price']}₽",
        approve_payment(user_id, tariff_id),
    )
    await safe_edit(
        call,
        "✅ Заявка на продление отправлена\n\n⏳ Ожидайте подтверждения",
        back_to_menu(),
    )


# ===== TARIFF =====

@router.callback_query(F.data.startswith("tariff_"))
async def tariff(call: CallbackQuery) -> None:
    await call.answer()
    tariff_id = (call.data or "")[len("tariff_"):]
    tariff = settings.tariffs.get(tariff_id)
    if not tariff:
        return

    text = (
        f"{settings.payment_text}\n\n"
        f"📦 Тариф: {tariff['title']}\n"
        f"💰 Цена: {tariff['price']}₽\n"
        f"📅 Срок: {tariff['days']} дней\n\n"
        f"🆔 Ваш ID:\n{call.from_user.id}"
    )
    await safe_edit(call, text, tariff_payment(tariff_id, back_to="buy"))


# ===== PAID =====

@router.callback_query(F.data.startswith("paid_"))
async def paid(call: CallbackQuery, bot: Bot) -> None:
    if not await check_rate_limit(call, payment_limiter):
        return

    tariff_id = (call.data or "")[len("paid_"):]
    tariff = settings.tariffs.get(tariff_id)
    if not tariff:
        return

    user_id = call.from_user.id
    if await has_pending_payment(user_id):
        await call.answer("⏳ У тебя уже есть активная заявка", show_alert=True)
        return

    await call.answer()
    await add_pending_payment(user_id, tariff_id)

    username = await get_username(user_id) or "Без ника"
    await _notify_admins(
        bot,
        f"💰 Новая заявка\n\n"
        f"👤 {username}\n🆔 ID: {user_id}\n\n"
        f"📦 Тариф: {tariff['title']}\n💰 Сумма: {tariff['price']}₽",
        approve_payment(user_id, tariff_id),
    )
    await safe_edit(
        call, "✅ Заявка отправлена\n\n⏳ Ожидайте подтверждения", back_to_menu()
    )


# ===== APPROVE (админ подтверждает оплату/продление) =====

@router.callback_query(F.data.startswith("approve|"))
async def approve(call: CallbackQuery, bot: Bot) -> None:
    if call.from_user.id not in settings.admin_ids:
        return

    parts = (call.data or "").split("|")
    if len(parts) != 3:
        return
    _, user_id_str, tariff_id = parts
    user_id = int(user_id_str)

    tariff = settings.tariffs.get(tariff_id)
    if not tariff:
        return

    if not await has_pending_payment(user_id):
        await call.answer("⚠️ Заявка не найдена или уже обработана", show_alert=True)
        return

    pending = await get_pending_payment_info(user_id)
    if not pending or pending["tariff_id"] != tariff_id:
        await call.answer("⚠️ Тариф не совпадает с заявкой", show_alert=True)
        return

    days = tariff["days"]
    payment_type = pending["payment_type"]

    await set_subscription(user_id, days)
    if payment_type == "renew":
        await extend_user(user_id, days)
    else:
        await create_user(user_id, days)
    await set_sub_disabled(user_id, False)
    await remove_pending_payment(user_id)

    type_label = "🔄 Продление" if payment_type == "renew" else "✅ Оплата"
    verb = "продлён" if payment_type == "renew" else "активирован"
    try:
        await bot.send_message(
            user_id,
            f"{type_label} подтверждено\n\n"
            f"📦 Тариф: {tariff['title']}\n"
            f"📅 Добавлено: {days} дней\n\n"
            f"🔑 VPN {verb}",
        )
    except Exception:
        pass

    await safe_edit(call, f"{type_label} подтверждено", back_to_menu())
    await call.answer("✅ Готово")


# ===== SUPPORT =====

@router.callback_query(F.data == "support")
async def support(call: CallbackQuery, state: FSMContext) -> None:
    if not await check_rate_limit(call, support_limiter):
        return
    await call.answer()
    await safe_edit(call, "💬 Напиши сообщение и мы ответим:", back_to_menu())
    await state.set_state(UserStates.waiting_for_support)


# ===== SEND SUPPORT =====

@router.message(UserStates.waiting_for_support)
async def send_support(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.from_user is None:
        return
    if not await check_rate_limit(message, support_limiter):
        return

    user_id = message.from_user.id
    text = message.text
    if not text:
        await message.answer("❌ Пустое сообщение")
        return

    await state.clear()
    if len(text) > 1000:
        text = text[:1000] + "...\n[обрезано]"

    username = await get_username(user_id) or "Без ника"
    await _notify_admins(
        bot,
        f"💬 Новое сообщение\n\n"
        f"👤 {username}\n🆔 ID: {user_id}\n\n📩 Сообщение:\n{text}",
        reply_to_user(user_id),
    )
    await message.answer("✅ Сообщение отправлено")


# ===== REPLY (админ отвечает на обращение) =====

@router.callback_query(F.data.startswith("reply|"))
async def reply(call: CallbackQuery, state: FSMContext) -> None:
    if call.from_user.id not in settings.admin_ids:
        return

    parts = (call.data or "").split("|")
    if len(parts) != 2:
        return
    user_id = int(parts[1])

    await call.answer()
    await state.set_state(AdminStates.waiting_for_reply)
    await state.update_data(reply_to=user_id)
    if isinstance(call.message, Message):
        await call.message.answer(f"✉️ Ответ пользователю {user_id}:")


# ===== SEND REPLY =====

@router.message(AdminStates.waiting_for_reply)
async def send_reply(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    user_id = data.get("reply_to")
    await state.clear()

    if user_id is None:
        return
    try:
        await bot.send_message(
            user_id, f"💬 Ответ поддержки\n\n{message.text}"
        )
        await message.answer("✅ Ответ отправлен")
    except Exception as e:
        logger.error("SEND REPLY ERROR: %s", e)
        await message.answer("❌ Не удалось отправить ответ")


# ===== TOKEN (Мой VPN) =====

@router.callback_query(F.data == "token")
async def token(call: CallbackQuery) -> None:
    await call.answer()
    user_id = call.from_user.id

    if not await has_sub(user_id):
        if await is_sub_disabled(user_id):
            await call.answer(
                "⏸ Подписка отключена — продлите для восстановления", show_alert=True
            )
        else:
            await call.answer("❌ Нет подписки", show_alert=True)
        return

    sub = await get_vpn_data(user_id)
    if not sub:
        await call.answer("❌ Не удалось получить данные VPN", show_alert=True)
        return

    await safe_edit(call, f"🔑 Твой VPN\n\n{sub}", back_to_menu())
    if isinstance(call.message, Message):
        await call.message.answer_photo(generate_qr(sub))


# ===== SERVER STATUS =====

@router.callback_query(F.data == "server_status")
async def server_status(call: CallbackQuery) -> None:
    await call.answer()
    lines = ["🖥 Статус серверов\n"]

    timeout = aiohttp.ClientTimeout(total=5)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for server in settings.servers:
            try:
                async with session.get(server["url"], ssl=False):
                    status = "🟢 Онлайн"
            except TimeoutError:
                status = "🔴 Таймаут"
            except Exception as e:
                logger.debug("SERVER STATUS [%s]: %s", server["name"], e)
                status = "🔴 Недоступен"
            lines.append(f"{server['name']}\n{status}")

    await safe_edit(call, "\n\n".join(lines), back_to_menu())
