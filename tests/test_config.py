"""
Тесты bot/config.py — парсинг списков из .env, свойства, валидаторы.

Регрессия на баг: list-поля раньше падали на json.loads в pydantic-settings
до field_validator. Эти тесты фиксируют корректный разбор "1,2,3".
"""

import pytest
from pydantic import ValidationError

from bot.config import Settings, get_settings


def _settings(**override) -> Settings:
    # Обязательные поля берутся из окружения (conftest), здесь переопределяем точечно
    return Settings(**override)


class TestListParsing:
    def test_admin_ids(self):
        assert _settings(admin_ids="10,20,30").admin_ids == [10, 20, 30]

    def test_admin_ids_ignores_non_digits(self):
        assert _settings(admin_ids="1,abc,2, ,3").admin_ids == [1, 2, 3]

    def test_admin_ids_empty(self):
        assert _settings(admin_ids="").admin_ids == []

    def test_admin_ids_accepts_list(self):
        assert _settings(admin_ids=[5, 6]).admin_ids == [5, 6]

    def test_admin_usernames(self):
        assert _settings(admin_usernames="a, b ,c").admin_usernames == ["a", "b", "c"]

    def test_vless_inbound_ids(self):
        assert _settings(vless_inbound_ids="1,2,9").vless_inbound_ids == [1, 2, 9]


class TestSslVerify:
    def test_true(self):
        assert _settings(panel_verify="true").ssl_verify is True

    def test_false(self):
        assert _settings(panel_verify="false").ssl_verify is False

    def test_case_insensitive(self):
        assert _settings(panel_verify="FALSE").ssl_verify is False

    def test_path_passthrough(self):
        assert _settings(panel_verify="/etc/ssl/ca.crt").ssl_verify == "/etc/ssl/ca.crt"


class TestServers:
    def test_only_servers_with_url(self):
        s = _settings(
            server_1_name="A", server_1_url="http://a",
            server_2_name="B", server_2_url="",
        )
        assert s.servers == [{"name": "A", "url": "http://a"}]

    def test_no_servers(self):
        s = _settings(server_1_url="", server_2_url="")
        assert s.servers == []


class TestTariffs:
    def test_four_tariffs(self):
        assert len(_settings().tariffs) == 4

    def test_tariff_shape(self):
        t = _settings().tariffs["1"]
        assert {"title", "days", "price"} <= set(t)


class TestValidators:
    def test_empty_panel_url_raises(self):
        with pytest.raises(ValidationError):
            _settings(panel_url="")

    def test_empty_api_token_raises(self):
        with pytest.raises(ValidationError):
            _settings(api_token="")


class TestPaymentText:
    def test_contains_admins_and_numbers(self):
        s = _settings(
            admin_usernames="boss",
            sbp_number="+79990000000",
            card_number="2200111122223333",
        )
        text = s.payment_text
        assert "@boss" in text
        assert "+79990000000" in text
        assert "2200111122223333" in text


def test_get_settings_is_cached():
    assert get_settings() is get_settings()
