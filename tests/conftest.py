"""
Общая конфигурация тестов.

ВАЖНО: переменные окружения выставляются ДО импорта bot.config,
чтобы pydantic-settings собрал детерминированный Settings, не завися
от реального .env и боевой панели. БД — in-memory.
"""

import os

os.environ.setdefault("BOT_TOKEN", "123456:test-token")
os.environ.setdefault("PANEL_URL", "https://panel.example.com")
os.environ.setdefault("API_TOKEN", "test_token")
os.environ.setdefault("SUB_BASE_URL", "https://sub.example.com/sub")
os.environ.setdefault("ADMIN_IDS", "1,2,3")
os.environ.setdefault("ADMIN_USERNAMES", "admin1,admin2")
os.environ.setdefault("VLESS_INBOUND_IDS", "1,2")
os.environ.setdefault("HYSTERIA_INBOUND_ID", "3")
os.environ.setdefault("HYSTERIA_ENABLED", "false")
os.environ.setdefault("DB_PATH", ":memory:")

import pytest_asyncio  # noqa: E402

from bot.database import db as _db  # noqa: E402


@pytest_asyncio.fixture
async def fresh_db():
    """Чистая in-memory БД на каждый тест."""
    await _db.init_db()
    try:
        yield _db
    finally:
        await _db.close_db()
