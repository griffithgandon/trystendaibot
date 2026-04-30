import telebot
from config import BOT_TOKEN
from handlers.user import register_handlers
from handlers.admin_panel import register_admin

bot = telebot.TeleBot(BOT_TOKEN)

register_handlers(bot)
register_admin(bot)

print("Bot started polling")
bot.infinity_polling()