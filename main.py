from telebot import TeleBot
from handlers.user_handlers import register_handlers
from handlers.admin_handlers import register_admin
from config import BOT_TOKEN
import time

bot = TeleBot(BOT_TOKEN)

register_handlers(bot)
register_admin(bot)

print("🚀 BOT START")

while True:
    try:
        bot.infinity_polling()
    except Exception as e:
        print("CRASH:", e)
        time.sleep(3)