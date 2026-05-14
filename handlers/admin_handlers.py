from telebot import types
from config import ADMIN_ID
from database.db import (
    get_username, get_telegram_username, get_sub_until,
    set_subscription, remove_sub, get_pending_payments,
    remove_pending_payment, get_total_users, get_total_subs,
    get_recent_users, get_all_user_ids,
)
from services.vpn import create_user, delete_user, get_online_users
import time


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_ID


def safe_edit(bot, call, text: str, markup=None):
    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
    except Exception as e:
        if "message is not modified" not in str(e):
            print("EDIT ERROR:", e)


# ===== UI =====
def admin_menu() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"))
    markup.add(types.InlineKeyboardButton("🟢 Онлайн", callback_data="admin_online"))
    markup.add(types.InlineKeyboardButton("💰 Заявки", callback_data="pending_list"))
    markup.add(types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"))
    markup.add(types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"))
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu"))
    return markup


def back() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
    return markup


# ===== HANDLERS =====
def register_admin_handlers(bot):

    # ===== ADMIN PANEL =====
    @bot.callback_query_handler(func=lambda c: c.data == "admin_panel")
    def admin_panel(call):
        if not is_admin(call.from_user.id):
            return
        bot.answer_callback_query(call.id)
        safe_edit(bot, call, "⚙️ Админ панель", admin_menu())

    # ===== USERS LIST =====
    @bot.callback_query_handler(func=lambda c: c.data == "admin_users")
    def users(call):
        if not is_admin(call.from_user.id):
            return
        bot.answer_callback_query(call.id)

        rows = get_recent_users(20)
        markup = types.InlineKeyboardMarkup()

        for (user_id,) in rows:
            username = get_username(user_id) or "Без ника"
            markup.add(
                types.InlineKeyboardButton(
                    f"👤 {username} | {user_id}",
                    callback_data=f"user_{user_id}"
                )
            )

        markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
        safe_edit(bot, call, "👥 Последние пользователи:", markup)

    # ===== USER MENU =====
    @bot.callback_query_handler(func=lambda c: c.data.startswith("user_"))
    def user_menu(call):
        if not is_admin(call.from_user.id):
            return
        bot.answer_callback_query(call.id)

        try:
            user_id = int(call.data[len("user_"):])
        except ValueError:
            return

        username = get_username(user_id) or "Без ника"
        tg_username = get_telegram_username(user_id) or "нет"
        sub_until = get_sub_until(user_id)

        sub_text = (
            time.strftime("%d.%m.%Y %H:%M", time.localtime(sub_until))
            if sub_until > int(time.time())
            else "Нет подписки"
        )

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Выдать", callback_data=f"give_{user_id}"),
            types.InlineKeyboardButton("❌ Удалить", callback_data=f"remove_{user_id}")
        )
        markup.add(types.InlineKeyboardButton("♻️ Пересоздать", callback_data=f"recreate_{user_id}"))
        markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_users"))

        safe_edit(
            bot, call,
            f"👤 Пользователь\n\n"
            f"🪪 Ник: {username}\n"
            f"🌐 Telegram: @{tg_username}\n"
            f"🆔 ID: {user_id}\n\n"
            f"💎 Подписка:\n{sub_text}",
            markup
        )

    # ===== GIVE =====
    @bot.callback_query_handler(func=lambda c: c.data.startswith("give_"))
    def give(call):
        if not is_admin(call.from_user.id):
            return
        bot.answer_callback_query(call.id)

        try:
            user_id = int(call.data[len("give_"):])
        except ValueError:
            return

        try:
            set_subscription(user_id, 30)
            create_user(user_id, 30)
            safe_edit(bot, call, f"✅ Выдано {user_id}", back())
            bot.send_message(user_id, "✅ Подписка выдана")
        except Exception as e:
            print("GIVE ERROR:", e)

    # ===== REMOVE =====
    @bot.callback_query_handler(func=lambda c: c.data.startswith("remove_"))
    def remove(call):
        if not is_admin(call.from_user.id):
            return
        bot.answer_callback_query(call.id)

        try:
            user_id = int(call.data[len("remove_"):])
        except ValueError:
            return

        try:
            delete_user(user_id)
            remove_sub(user_id)
            safe_edit(bot, call, f"❌ Пользователь {user_id} удалён", back())
            try:
                bot.send_message(user_id, "❌ Ваша подписка удалена")
            except Exception:
                pass
        except Exception as e:
            print("DELETE ERROR:", e)

    # ===== RECREATE =====
    @bot.callback_query_handler(func=lambda c: c.data.startswith("recreate_"))
    def recreate(call):
        if not is_admin(call.from_user.id):
            return
        bot.answer_callback_query(call.id)

        try:
            user_id = int(call.data[len("recreate_"):])
        except ValueError:
            return

        try:
            delete_user(user_id)
            set_subscription(user_id, 30)
            create_user(user_id, 30)
            safe_edit(bot, call, f"♻️ Пересоздан {user_id}", back())
            bot.send_message(user_id, "♻️ VPN пересоздан")
        except Exception as e:
            print("RECREATE ERROR:", e)

    # ===== STATS =====
    @bot.callback_query_handler(func=lambda c: c.data == "admin_stats")
    def stats(call):
        if not is_admin(call.from_user.id):
            return
        bot.answer_callback_query(call.id)

        total = get_total_users()
        active = get_total_subs()

        safe_edit(
            bot, call,
            f"📊 Статистика\n\n"
            f"👥 Всего пользователей: {total}\n"
            f"💎 Активных подписок: {active}",
            back()
        )

    # ===== ONLINE =====
    @bot.callback_query_handler(func=lambda c: c.data == "admin_online")
    def online(call):
        if not is_admin(call.from_user.id):
            return
        bot.answer_callback_query(call.id)

        print("STEP 1: getting clients")
        clients = get_online_users()
        print("STEP 2: clients =", clients)

        if clients is None:
            safe_edit(bot, call, "❌ Не удалось получить данные с панели", back())
            return

        if not clients:
            safe_edit(bot, call, "🟡 Сейчас никого нет онлайн", back())
            return

        seen = set()
        lines = []
        now = int(time.time())

        for email in clients:
            uid_str = email.split("_")[0]
            if uid_str in seen:
                continue
            seen.add(uid_str)
            print("STEP 3: processing uid", uid_str)

            try:
                uid = int(uid_str)
                print("STEP 4: get_username")
                username = get_username(uid) or "Без ника"
                print("STEP 5: get_telegram_username")
                tg = get_telegram_username(uid) or "—"
                print("STEP 6: get_sub_until")
                sub_until = get_sub_until(uid)
                print("STEP 7: sub_until =", sub_until)

                if sub_until > now:
                    days_left = (sub_until - now) // 86400
                    hours_left = ((sub_until - now) % 86400) // 3600
                    expire_date = time.strftime("%d.%m.%Y", time.localtime(sub_until))
                    remain = f"{days_left}д {hours_left}ч" if days_left > 0 else f"{hours_left}ч"
                    sub_info = f"до {expire_date} (осталось {remain})"
                else:
                    sub_info = "⚠️ истекла"

                lines.append(f"• {username} | @{tg} | {uid}\n  💎 {sub_info}")

            except ValueError:
                lines.append(f"• {email}")

        print("STEP 8: building text")
        text = f"🟢 Онлайн сейчас: {len(seen)}\n\n" + "\n\n".join(lines)

        if len(text) > 4000:
            text = text[:4000] + "\n…"

        print("STEP 9: safe_edit")
        safe_edit(bot, call, text, back())
        print("STEP 10: done")

    # ===== PENDING PAYMENTS =====
    @bot.callback_query_handler(func=lambda c: c.data == "pending_list")
    def pending_list(call):
        if not is_admin(call.from_user.id):
            return
        bot.answer_callback_query(call.id)

        payments = get_pending_payments()

        if not payments:
            safe_edit(bot, call, "❌ Активных заявок нет", back())
            return

        markup = types.InlineKeyboardMarkup()
        text = "💰 Активные заявки\n"

        for user_id, tariff_id, created_at, payment_type in payments:
            username = get_username(user_id) or "Без ника"
            type_label = "🔄 Продление" if payment_type == "renew" else "🆕 Новая"
            text += f"\n{type_label}\n👤 {username}\n🆔 ID: {user_id}\n"
            markup.add(
                types.InlineKeyboardButton(
                    f"{type_label} | {user_id}",
                    callback_data=f"user_{user_id}"
                )
            )

        markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
        safe_edit(bot, call, text, markup)

    # ===== BROADCAST =====
    @bot.callback_query_handler(func=lambda c: c.data == "admin_broadcast")
    def broadcast(call):
        if not is_admin(call.from_user.id):
            return
        bot.answer_callback_query(call.id)

        msg = bot.send_message(call.message.chat.id, "✍️ Введи текст рассылки")
        bot.register_next_step_handler(msg, send_broadcast)

    def send_broadcast(message):
        if not is_admin(message.from_user.id):
            return

        rows = get_all_user_ids()
        sent = 0
        failed = 0

        for (uid,) in rows:
            try:
                bot.send_message(uid, message.text)
                sent += 1
                time.sleep(0.05)
            except Exception:
                failed += 1

        bot.send_message(
            message.chat.id,
            f"✅ Отправлено: {sent}\n❌ Не доставлено: {failed}"
        )