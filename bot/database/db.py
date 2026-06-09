import aiosqlite

from bot.config import get_settings

settings = get_settings()

# Глобальное соединение — открывается один раз при старте бота
_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        raise RuntimeError(
            "База данных не инициализирована. Вызови init_db() при старте."
        )
    return _db


async def init_db() -> None:
    global _db
    _db = await aiosqlite.connect(settings.db_path)
    _db.row_factory = aiosqlite.Row  # строки как dict, не tuple
    await _run_migrations(_db)


async def close_db() -> None:
    global _db
    if _db:
        await _db.close()
        _db = None


async def _run_migrations(db: aiosqlite.Connection) -> None:
    await db.executescript("""
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS users (
            user_id            INTEGER PRIMARY KEY,
            username           TEXT,
            telegram_username  TEXT,
            sub_until          INTEGER DEFAULT 0,
            reminded           INTEGER DEFAULT 0,
            trial_used         INTEGER DEFAULT 0,
            sub_disabled       INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS pending_payments (
            user_id      INTEGER PRIMARY KEY,
            tariff_id    TEXT,
            created_at   INTEGER,
            payment_type TEXT DEFAULT 'new'
        );
    """)
    await db.commit()

    # Накатываем колонки которых могло не быть в старой БД
    migrations = [
        "ALTER TABLE users ADD COLUMN reminded INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN trial_used INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN sub_disabled INTEGER DEFAULT 0",
    ]

    for sql in migrations:
        try:
            await db.execute(sql)
            await db.commit()
        except aiosqlite.OperationalError:
            pass  # колонка уже существует