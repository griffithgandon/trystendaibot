import os
from dotenv import load_dotenv

INBOUND_IDS = 1,2,3,4

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_ID = list(map(int, os.getenv("ADMIN_ID").split(",")))

DB_PATH = os.getenv('DB_PATH')

SUB_BASE_URL = os.getenv("SUB_BASE_URL")
PANEL_URL = os.getenv("PANEL_URL")
DOMAIN = os.getenv("DOMAIN")
PORT = int(os.getenv("PORT"))

USERNAME = os.getenv("PANEL_LOGIN")
PASSWORD = os.getenv("PANEL_PASSWORD")


# CARD_NUMBER = os.getenv("CARD_NUMBER")