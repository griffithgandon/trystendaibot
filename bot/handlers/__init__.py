"""Сбор всех роутеров бота."""

from aiogram import Router

from bot.handlers.admin import router as admin_router
from bot.handlers.user import router as user_router


def get_routers() -> list[Router]:
    # Порядок: user первым, admin вторым. Колбэки не пересекаются,
    # admin-роутер дополнительно закрыт фильтром IsAdmin.
    return [user_router, admin_router]
