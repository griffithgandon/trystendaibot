# Telegram VPN Bot
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://github.com/astral-sh/ruff)

## User Features

- User profile
- VPN purchase system
- Tariff selection
- Subscription status
- VPN config retrieval
- QR-code generation
- Built-in support chat
- Trial subscriptions

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

## Tech Stack

- Python 3.14+
- [aiogram 3](https://docs.aiogram.dev/) (async)
- SQLite (aiosqlite)
- pydantic-settings (конфигурация)
- APScheduler (фоновые задачи)
- [uv](https://docs.astral.sh/uv/) (управление зависимостями)
- 3X-UI API (VLESS + Hysteria2)

# Установка

## Клонировать репозиторий

```bash
git clone https://github.com/griffithgandon/trystendaibot
cd trystendaibot
```

## Установить зависимости

```bash
uv sync
```

## Конфигурация (.env)

Вся конфигурация задаётся через переменные окружения в файле `.env`
(файла нет в репозитории — секреты). Скопируй шаблон и заполни:

```bash
cp .env.example .env
```

Минимально необходимые переменные:

```text
BOT_TOKEN=...        # токен бота из @BotFather
ADMIN_IDS=1,2        # Telegram ID администраторов через запятую
PANEL_URL=...        # полный URL панели 3X-UI (с webBasePath, без слэша в конце)
API_TOKEN=...        # Bearer-токен панели: Settings -> API
SUB_BASE_URL=...     # базовый URL подписки (без слэша в конце)
```

Остальное (платёжные реквизиты, пробный период, серверы статуса) — см.
комментарии в [.env.example](.env.example).

**Inbound ID определяются автоматически**: бот запрашивает
`/panel/api/inbounds/list` и находит VLESS/Hysteria2-инбаунды по протоколу.
`VLESS_INBOUND_IDS` / `HYSTERIA_INBOUND_ID` в `.env` нужны только если
хочешь ограничить выдачу конкретными инбаундами.

Тарифы заданы в `bot/config.py` (свойство `Settings.tariffs`).

## Запуск бота

```bash
uv run python main.py
```

## Тесты и линтеры

```bash
uv run pytest          # тесты (без сети и реальной панели)
uv run ruff check .    # линтер
uv run mypy bot/       # типы
```

# База данных

SQLite, создаётся автоматически при первом запуске. Таблицы:
- users
- pending_payments

# Структура проекта

```text
bot/
    config.py            # Settings (pydantic-settings, .env)
    states.py            # FSM-состояния
    scheduler.py         # APScheduler (проверка подписок раз в час)
    database/
        db.py            # соединение и миграции (aiosqlite)
        repo.py          # запросы к БД
    handlers/
        user.py          # пользовательский роутер
        admin.py         # админский роутер (фильтр IsAdmin)
    keyboards/
        user.py
        admin.py
    middlewares/
        throttling.py    # анти-флуд (rate limit)
        error_handler.py # глобальный обработчик ошибок
    services/
        vpn.py           # 3X-UI API (async, автодискавери инбаундов)
        sub_checker.py   # напоминания и отключение истёкших подписок
    utils/
        qr.py            # QR-коды конфигов

main.py                  # точка входа (Bot, Dispatcher, polling)
tests/                   # pytest + pytest-asyncio
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
