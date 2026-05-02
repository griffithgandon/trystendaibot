import telebot
from config import BOT_TOKEN
from handlers.user_handlers import register_handlers
from handlers.admin_handlers import register_admin

bot = telebot.TeleBot(BOT_TOKEN)

register_handlers(bot)
register_admin(bot)

print('Бот начал опрашивать сервер...')

bot.infinity_polling(skip_pending=True)