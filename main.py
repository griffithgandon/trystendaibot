import time
import telebot

from config import BOT_TOKEN
from handlers.user_handlers import register_handlers
from handlers.admin_handlers import register_admin_handlers

bot = telebot.TeleBot(BOT_TOKEN)

register_handlers(bot)
register_admin_handlers(bot)


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