import telebot
from config import BOT_TOKEN
from handlers.user import register_handlers

bot = telebot.TeleBot(BOT_TOKEN)

register_handlers(bot)

print("TRYSTENDAI")

bot.infinity_polling()