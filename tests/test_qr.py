"""Тесты bot/utils/qr.py — генерация QR как aiogram BufferedInputFile."""

from aiogram.types import BufferedInputFile

from bot.utils.qr import generate_qr

PNG_MAGIC = b"\x89PNG"


def test_returns_buffered_input_file():
    assert isinstance(generate_qr("vless://test"), BufferedInputFile)


def test_is_png():
    assert generate_qr("https://example.com").data[:4] == PNG_MAGIC


def test_default_filename():
    assert generate_qr("x").filename == "qr.png"


def test_custom_filename():
    assert generate_qr("x", filename="conf.png").filename == "conf.png"


def test_different_inputs_differ():
    assert generate_qr("config_1").data != generate_qr("config_2").data


def test_empty_string_does_not_crash():
    assert generate_qr("").data[:4] == PNG_MAGIC


def test_long_string():
    long_url = "vless://" + "a" * 500 + "?type=tcp&security=reality"
    assert len(generate_qr(long_url).data) > 0
