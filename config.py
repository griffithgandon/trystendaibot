import os
from dotenv import load_dotenv

load_dotenv()


# ===== HELPERS =====
def get_list(key):
    value = os.getenv(key, "")
    return [int(x) for x in value.split(",") if x.strip().isdigit()]


def get_int(key, default=0):
    try:
        return int(os.getenv(key, default))
    except:
        return default


def get_bool(key, default=False):
    return os.getenv(key, str(default)).lower() == "true"


# ===== BOT =====
BOT_TOKEN = os.getenv("BOT_TOKEN", "")


# ===== ADMIN =====
ADMIN_ID = get_list("ADMIN_ID")


# ===== DB =====
DB_PATH = os.getenv("DB_PATH", "database/bot.db")


# ===== XRAY PANEL =====
PANEL_URL = os.getenv("PANEL_URL")
API_TOKEN = os.getenv("API_TOKEN")

INBOUND_IDS = get_list("INBOUND_IDS")


# ===== SUB =====
SUB_BASE_URL = os.getenv("SUB_BASE_URL", "")
DOMAIN = os.getenv("DOMAIN", "")
PORT = get_int("PORT", 443)


# ===== HYSTERIA =====
HYSTERIA_ENABLED = get_bool("HYSTERIA_ENABLED")

HYSTERIA_API_URL = os.getenv("HYSTERIA_API_URL", "")
HYSTERIA_API_KEY = os.getenv("HYSTERIA_API_KEY", "")

HYSTERIA_HOST = os.getenv("HYSTERIA_HOST", "")
HYSTERIA_PORT = get_int("HYSTERIA_PORT", 443)
HYSTERIA_SNI = os.getenv("HYSTERIA_SNI", "")


# ===== PAYMENT =====
PAYMENT_TEXT = os.getenv("PAYMENT_TEXT") or """
💳 Оплата VPN

💰 Цена: 100₽ / 30 дней

Способы оплаты:
— СБП: +79682753651
— Карта: 2200 0000 0000 0000
— В комментариях оплаты укажите свой id

📌 После оплаты нажми кнопку ниже
"""


# ===== DEBUG =====
print("=== CONFIG CHECK ===")

print("PANEL_URL:", PANEL_URL)
print("API_TOKEN:", bool(API_TOKEN))

print("INBOUND_IDS:", INBOUND_IDS)

print("DOMAIN:", DOMAIN)
print("SUB_BASE_URL:", SUB_BASE_URL)

print("====================")