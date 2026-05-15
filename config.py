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
PANEL_URL = os.getenv("PANEL_URL", "")
API_TOKEN = os.getenv("API_TOKEN", "")

# VLESS_INBOUND_IDS — список через запятую, например: 1,2,3,9,10,11
VLESS_INBOUND_IDS = get_list("VLESS_INBOUND_IDS")
HYSTERIA_INBOUND_ID = int(os.getenv("HYSTERIA_INBOUND_ID", "0"))


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


# ===== TARIFFS =====
TARIFFS = {
    "1": {
        "title": "30 дней — 150₽",
        "days": 30,
        "price": 150
    },
    "2": {
        "title": "90 дней — 450₽",
        "days": 90,
        "price": 450
    },
    "3": {
        "title": "180 дней — 900₽",
        "days": 180,
        "price": 900
    },
    "4": {
        "title": "360 дней — 1500₽",
        "days": 360,
        "price": 1500
    }
}


# ===== PAYMENT =====
SBP_NUMBER = os.getenv("SBP_NUMBER", "")
CARD_NUMBER = os.getenv("CARD_NUMBER", "")

ADMIN_USERNAMES = os.getenv("ADMIN_USERNAMES", "").split(",")
admins = "\n".join([f"@{x.strip()}" for x in ADMIN_USERNAMES if x.strip()])

PAYMENT_TEXT = f"""
💳 Оплата VPN

📌 После оплаты нажмите кнопку ниже

Способы оплаты:

💸 СБП:
{SBP_NUMBER}

💳 Карта:
{CARD_NUMBER}

Перед оплатой напишите одному из админов 👉 {admins}

📝 В комментарии к переводу укажите свой Telegram ID
"""


# ===== SUPPORT =====
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@support")


# ===== DEBUG =====
print("=== CONFIG CHECK ===")
print("PANEL_URL:", PANEL_URL)
print("API_TOKEN:", bool(API_TOKEN))
print("VLESS_INBOUND_IDS:", VLESS_INBOUND_IDS)
print("HYSTERIA_INBOUND_ID:", HYSTERIA_INBOUND_ID)
print("DOMAIN:", DOMAIN)
print("SUB_BASE_URL:", SUB_BASE_URL)
print("HYSTERIA_ENABLED:", HYSTERIA_ENABLED)
print("TARIFFS:", TARIFFS)
print("====================")


# ===== SERVERS =====
SERVERS = [
    {"name": os.getenv("SERVER1_NAME", "Сервер 1"), "url": os.getenv("SERVER1_URL", "")},
    {"name": os.getenv("SERVER2_NAME", "Сервер 2"), "url": os.getenv("SERVER2_URL", "")},
]

# ===== TLS =====
PANEL_VERIFY = os.getenv("PANEL_VERIFY", "true")

if PANEL_VERIFY.lower() == "false":
    SSL_VERIFY = False
elif PANEL_VERIFY.lower() == "true":
    SSL_VERIFY = True
else:
    SSL_VERIFY = PANEL_VERIFY  # путь к CA-файлу, например "/etc/ssl/certs/panel.crt"