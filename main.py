import time
import telebot

from config import BOT_TOKEN
from handlers.user_handlers import register_handlers
from handlers.admin_handlers import register_admin_handlers

from services.sub_checker import check_subscriptions
import threading

bot = telebot.TeleBot(BOT_TOKEN)

register_handlers(bot)
register_admin_handlers(bot)

def sub_loop():

    while True:

        try:
            check_subscriptions(bot)

        except Exception as e:
            print("SUB LOOP ERROR:", e)

        time.sleep(3600)


threading.Thread(
    target=sub_loop,
    daemon=True
).start()

while True:
    try:
        print("BOT STARTED")

        bot.infinity_polling(
            timeout=20,
            long_polling_timeout=20,
            skip_pending=True
        )

    except Exception as e:
        print("CRASH:", e)
        time.sleep(3)