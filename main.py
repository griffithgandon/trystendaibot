import telebot
from config import BOT_TOKEN
from handlers.user import register_handlers
from handlers.admin_panel import register_admin

bot = telebot.TeleBot(BOT_TOKEN)

register_handlers(bot)
register_admin(bot)

bot.infinity_polling(skip_pending=True)