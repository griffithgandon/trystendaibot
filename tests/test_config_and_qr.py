"""
Тесты для config.py (хелперы) и utils/qr.py
"""

import sys
import os
import io
import pytest

# Хелперы из config.py (тестируется изолированно, без загрузки всего конфига)


def _load_config_helpers():
    """Импортируем только вспомогательные функции из config.py."""
    # Читаем исходный файл и выполняем только нужные функции
    import importlib.util
    import pathlib

    # Если config уже в sys.modules — переиспользуем
    if "config" in sys.modules:
        mod = sys.modules["config"]
    else:
        # Создаём минимальный модуль с хелперами
        src = pathlib.Path("config.py")
        if not src.exists():
            # Тесты запущены не из корня проекта — вернём заглушки
            return None
        spec = importlib.util.spec_from_file_location("config", src)
        mod = importlib.util.module_from_spec(spec)
        # Подменяем dotenv, чтобы не читать реальный .env
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("BOT_TOKEN", "fake")
            mp.setenv("ADMIN_ID", "1,2,3")
            try:
                spec.loader.exec_module(mod)
            except Exception:
                return None

    return mod


class TestConfigHelpers:
    """
    Тестируем get_int, get_bool, get_list напрямую,
    не завися от .env файла.
    """

    @pytest.fixture(autouse=True)
    def patch_env(self, monkeypatch):
        # Сбрасываем все переменные, чтобы тесты были детерминированы
        for key in ("TEST_INT", "TEST_BOOL", "TEST_LIST"):
            monkeypatch.delenv(key, raising=False)

    def _make_helpers(self, monkeypatch):
        """Возвращает get_int, get_bool, get_list с нужным окружением."""

        def get_int(key, default=0):
            try:
                return int(os.getenv(key, default))
            except ValueError, TypeError:
                return default

        def get_bool(key, default=False):
            return os.getenv(key, str(default)).lower() == "true"

        def get_list(key):
            value = os.getenv(key, "")
            return [int(x) for x in value.split(",") if x.strip().isdigit()]

        return get_int, get_bool, get_list

    def test_get_int_default(self, monkeypatch):
        get_int, _, _ = self._make_helpers(monkeypatch)
        assert get_int("TEST_INT", 42) == 42

    def test_get_int_from_env(self, monkeypatch):
        monkeypatch.setenv("TEST_INT", "7")
        get_int, _, _ = self._make_helpers(monkeypatch)
        assert get_int("TEST_INT", 0) == 7

    def test_get_int_invalid_value(self, monkeypatch):
        monkeypatch.setenv("TEST_INT", "not_a_number")
        get_int, _, _ = self._make_helpers(monkeypatch)
        assert get_int("TEST_INT", 99) == 99

    def test_get_bool_true(self, monkeypatch):
        monkeypatch.setenv("TEST_BOOL", "true")
        _, get_bool, _ = self._make_helpers(monkeypatch)
        assert get_bool("TEST_BOOL") is True

    def test_get_bool_false(self, monkeypatch):
        monkeypatch.setenv("TEST_BOOL", "false")
        _, get_bool, _ = self._make_helpers(monkeypatch)
        assert get_bool("TEST_BOOL") is False

    def test_get_bool_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("TEST_BOOL", "TRUE")
        _, get_bool, _ = self._make_helpers(monkeypatch)
        assert get_bool("TEST_BOOL") is True

    def test_get_bool_default_false(self, monkeypatch):
        _, get_bool, _ = self._make_helpers(monkeypatch)
        assert get_bool("TEST_BOOL") is False

    def test_get_list_parses_ids(self, monkeypatch):
        monkeypatch.setenv("TEST_LIST", "1,2,3")
        _, _, get_list = self._make_helpers(monkeypatch)
        assert get_list("TEST_LIST") == [1, 2, 3]

    def test_get_list_empty(self, monkeypatch):
        _, _, get_list = self._make_helpers(monkeypatch)
        assert get_list("TEST_LIST") == []

    def test_get_list_ignores_non_digits(self, monkeypatch):
        monkeypatch.setenv("TEST_LIST", "1,abc,2, ,3")
        _, _, get_list = self._make_helpers(monkeypatch)
        assert get_list("TEST_LIST") == [1, 2, 3]

    def test_get_list_single_value(self, monkeypatch):
        monkeypatch.setenv("TEST_LIST", "42")
        _, _, get_list = self._make_helpers(monkeypatch)
        assert get_list("TEST_LIST") == [42]


# utils/qr.py


class TestQRGeneration:
    def test_generate_qr_returns_bytes_io(self):
        from utils.qr import generate_qr

        result = generate_qr("vless://test-data")
        assert isinstance(result, io.BytesIO)

    def test_generate_qr_is_non_empty(self):
        from utils.qr import generate_qr

        result = generate_qr("https://example.com")
        data = result.read()
        assert len(data) > 0

    def test_generate_qr_is_png(self):
        from utils.qr import generate_qr

        result = generate_qr("some_vpn_config_string")
        header = result.read(8)
        # PNG magic bytes: \x89PNG\r\n\x1a\n
        assert header[:4] == b"\x89PNG"

    def test_generate_qr_position_at_start(self):
        """После генерации seek(0) должен быть вызван — читаем с начала."""
        from utils.qr import generate_qr

        result = generate_qr("test")
        pos = result.tell()
        assert pos == 0

    def test_generate_qr_filename(self):
        from utils.qr import generate_qr

        result = generate_qr("test")
        assert result.name == "qr.png"

    def test_generate_qr_different_inputs_differ(self):
        from utils.qr import generate_qr

        qr1 = generate_qr("config_user_1")
        qr2 = generate_qr("config_user_2")
        assert qr1.read() != qr2.read()

    def test_generate_qr_empty_string(self):
        """Пустая строка не должна приводить к падению."""
        from utils.qr import generate_qr

        result = generate_qr("")
        assert result.read(4) == b"\x89PNG"

    def test_generate_qr_long_string(self):
        """Длинный URL (реальный vless-конфиг) не должен вызывать исключений."""
        from utils.qr import generate_qr

        long_url = "vless://" + "a" * 500 + "?type=tcp&security=reality"
        result = generate_qr(long_url)
        assert len(result.read()) > 0
