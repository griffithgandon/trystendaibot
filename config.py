import os
from dotenv import load_dotenv

load_dotenv()

# ===== BOT =====
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ===== ADMIN =====
ADMIN_ID = list(map(int, os.getenv("ADMIN_ID", "").split(",")))

# ===== DB =====
DB_PATH = os.getenv("DB_PATH", "database/bot.db")

# ===== VPN =====
PANEL_URL = os.getenv("PANEL_URL")
SUB_BASE_URL = os.getenv("SUB_BASE_URL")
DOMAIN = os.getenv("DOMAIN")
PORT = int(os.getenv("PORT", 443))

# ===== PANEL AUTH =====
USERNAME = os.getenv("PANEL_LOGIN")
PASSWORD = os.getenv("PANEL_PASSWORD")

# ===== INBOUNDS =====
INBOUND_IDS = list(map(int, os.getenv("INBOUND_IDS", "").split(",")))

# ===== DEBUG (чтобы больше не гадать) =====
print("CONFIG CHECK:")
print("PANEL_URL:", PANEL_URL)
print("USERNAME:", USERNAME)
print("PASSWORD:", PASSWORD)
print("INBOUND_IDS:", INBOUND_IDS)

#
PAYMENT_TEXT = """
💳 Оплата VPN

💰 Цена: 100₽ / 30 дней

Способы оплаты:
— СБП: +7XXXXXXXXXX
— Карта: 2200 0000 0000 0000

📌 После оплаты нажми кнопку ниже
"""