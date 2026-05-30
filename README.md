# Telegram VPN Bot
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
## User Features

- User profile
- VPN purchase system
- Tariff selection
- Subscription status
- VPN config retrieval
- QR-code generation
- Built-in support chat

## Admin Features

- Admin panel
- User management
- Approve subscriptions
- Remove subscriptions
- Recreate VPN configs
- Pending payment requests
- Broadcast messages
- User statistics
- Telegram username display

# Tech Stack

- Python
- pyTelegramBotAPI
- SQLite
- 3X-UI API

# Установка

## Клонировать репозиторий

```bash
git clone https://github.com/griffithgandon/trystendaibot
cd REPOSITORY
```

## Установить зависимости

```bash
pip install -r requirements.txt
```

## Настройка конфигурационного файла

Настройка конфига производится в `config.py`

## Конфигурация секретов в .env

Без секретов бот работать не будет. Этого файла нет в репозитории по понятным причинам, из за чего требуется вручную создать его и настроить по примеру снизу.
```text
BOT_TOKEN = "BOT_TOKEN" - токен бота из BotFather, с кавычками

ADMIN_ID=000000,000000 - телеграм ID администраторов

DB_PATH=database/bot.db - путь к базе данных. На данный момент можно не трогать

PANEL_URL=https://domain.com:port/panel_url - полный url к панели

DOMAIN=domain.com - ваш домен, при наличии такового

ADMIN_USERNAMES=Null - Юзернеймы администраторов из телеграма через запятую

PANEL_VERIFY=true

HYSTERIA_ENABLED=true

# ВАЖНО — без / в конце
SUB_BASE_URL=https://domain.com:port/sub_url

API_TOKEN=token - Апи токен панели.

# ===== PAYMENT =====
SBP_NUMBER=+79999999999
CARD_NUMBER=2200000000000000

# тарифы
TARIFF_1_TITLE=30 дней
TARIFF_1_PRICE=150
TARIFF_1_DAYS=30

TARIFF_2_TITLE=90 дней
TARIFF_2_PRICE=450
TARIFF_2_DAYS=90

TARIFF_3_TITLE=180 дней
TARIFF_3_PRICE=900
TARIFF_3_DAYS=180

TARIFF_4_TITLE=360 дней
TARIFF_4_PRICE=1500
TARIFF_4_DAYS=365

SERVER1_NAME=
SERVER1_URL=

SERVER2_NAME=
SERVER2_URL=
```
## Запуск бота

```bash
python main.py
```

# База данных

Бот автоматически создает следующие таблицы:
- users
- pending_payments

# Структура проекта

```text
database/
    db.py
    
handlers/
    admin_handlers.py
    user_handlers.py

services/
    sub_checker.py
    vpn.py
    
utils/
    error_handler.py
    qr.py
    rate_limiter.py
    
config.py
main.py
```

# Потенциальное развитие проекта

- Авто-продление подписок;
- Интеграция платежного шлюза;
- ~~Пробные подписки;~~ - Добавлено
- Реферальная система;
- Поддержка PostgreSQL;
- Система резервных копий.

# License

MIT License