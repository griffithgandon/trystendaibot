import os
from dotenv import load_dotenv

INBOUND_ID = 1

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_ID = list(
    map(int, os.getenv("ADMIN_ID").split(","))
)

# DB_PATH = os.getenv("DB_PATH", "bot.db")

PANEL_URL = os.getenv("PANEL_URL")
USERNAME = os.getenv("PANEL_LOGIN")
PASSWORD = os.getenv("PANEL_PASSWORD")

# CARD_NUMBER = os.getenv("CARD_NUMBER")