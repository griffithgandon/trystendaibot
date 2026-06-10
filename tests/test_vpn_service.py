"""
Тесты bot/services/vpn.py.

HTTP к панели не выполняется: мокируется единая точка vpn._request
(возвращает (status, json, text)). get_username мокируется отдельно,
чтобы не поднимать БД.
"""

import json
import time
from unittest.mock import AsyncMock, patch

from bot.services import vpn

DAY_MS = 86400 * 1000


# ===== Builders =====

def _vless_inbound(inbound_id: int, clients: list) -> dict:
    return {
        "id": inbound_id,
        "protocol": "vless",
        "settings": json.dumps({"clients": clients}),
    }


def _vless_client(user_id: int, *, enabled=True, sub_id="abc123", expiry=None) -> dict:
    if expiry is None:
        expiry = int(time.time() * 1000) + 30 * DAY_MS
    return {
        "id": f"uuid-{user_id}",
        "email": f"{user_id}_vless_1",
        "enable": enabled,
        "expiryTime": expiry,
        "subId": sub_id,
    }


def _fake_request(inbounds=None, *, post_ok=True, online=None, capture=None):
    """Возвращает async-заглушку для vpn._request, маршрутизирующую по url."""
    inbounds = inbounds or []

    async def fake(session, method, url, json_data=None):
        if method == "GET" and url.endswith("/inbounds/list"):
            return (200, {"success": True, "obj": inbounds}, "")
        if method == "GET" and "/inbounds/get/" in url:
            iid = int(url.rstrip("/").split("/")[-1])
            obj = next((ib for ib in inbounds if ib["id"] == iid), None)
            if obj is None:
                return (404, {"success": False}, "")
            return (200, {"success": True, "obj": obj}, "")
        if method == "POST" and url.endswith("/inbounds/onlines"):
            return (200, {"success": True, "obj": online}, "")
        # мутирующие POST (addClient/updateClient/update/delClient)
        if capture is not None:
            capture.append({"method": method, "url": url, "json": json_data})
        return (200 if post_ok else 500, {"success": post_ok}, "")

    return fake


def _clients_from(payload: dict) -> list:
    return json.loads(payload.get("json", {}).get("settings", "{}")).get("clients", [])


# ===== inbound discovery =====

class TestDiscoverIds:
    def test_filters_vless_and_first_hysteria(self):
        data = {
            "obj": [
                {"id": 1, "protocol": "vless"},
                {"id": 2, "protocol": "vmess"},
                {"id": 3, "protocol": "vless"},
                {"id": 4, "protocol": "hysteria2"},
                {"id": 5, "protocol": "hysteria2"},
            ]
        }
        vless, hy = vpn._discover_ids(data)
        assert vless == [1, 3]
        assert hy == 4  # первый hysteria-инбаунд

    def test_empty_panel(self):
        assert vpn._discover_ids({"obj": []}) == ([], 0)

    def test_skips_inbounds_without_id(self):
        data = {"obj": [{"protocol": "vless"}, {"id": 7, "protocol": "vless"}]}
        assert vpn._discover_ids(data) == ([7], 0)


class TestResolveInboundIds:
    async def test_env_override_skips_network(self, monkeypatch):
        # conftest: VLESS_INBOUND_IDS=1,2; hysteria выключена -> сеть не нужна
        async def boom(*a, **kw):
            raise AssertionError("сеть не должна вызываться при override")

        monkeypatch.setattr(vpn, "get_inbounds", boom)
        assert await vpn.resolve_inbound_ids() == ([1, 2], 3)

    async def test_discovers_when_env_empty(self, monkeypatch):
        monkeypatch.setattr(vpn.settings, "vless_inbound_ids", [])
        monkeypatch.setattr(vpn.settings, "hysteria_inbound_id", 0)
        inbounds = [
            {"id": 11, "protocol": "vless"},
            {"id": 12, "protocol": "hysteria2"},
        ]
        with patch.object(vpn, "_request", new=_fake_request(inbounds)):
            vless, hy = await vpn.resolve_inbound_ids()
        assert vless == [11]
        assert hy == 12

    async def test_panel_down_falls_back_to_env(self, monkeypatch):
        monkeypatch.setattr(vpn.settings, "vless_inbound_ids", [])

        async def fail(session, method, url, json_data=None):
            return (500, {"success": False}, "")

        with patch.object(vpn, "_request", new=fail):
            vless, hy = await vpn.resolve_inbound_ids()
        assert vless == []  # как в .env — пусто

    async def test_create_user_uses_discovered_inbounds(self, monkeypatch):
        monkeypatch.setattr(vpn.settings, "vless_inbound_ids", [])
        inbounds = [
            {"id": 21, "protocol": "vless", "settings": "{}"},
            {"id": 22, "protocol": "vless", "settings": "{}"},
        ]
        cap: list = []
        with (
            patch.object(vpn, "_request", new=_fake_request(inbounds, capture=cap)),
            patch.object(vpn, "get_username", new=AsyncMock(return_value="t")),
        ):
            assert await vpn.create_user(500, 30) is True
        add = [c for c in cap if c["url"].endswith("/addClient")]
        assert {c["json"]["id"] for c in add} == {21, 22}


# ===== get_vpn_data =====

class TestGetVpnData:
    async def test_returns_sub_url(self):
        inbounds = [_vless_inbound(1, [_vless_client(100, sub_id="mysub")])]
        with patch.object(vpn, "_request", new=_fake_request(inbounds)):
            assert await vpn.get_vpn_data(100) == "https://sub.example.com/sub/mysub"

    async def test_none_when_not_found(self):
        with patch.object(vpn, "_request", new=_fake_request([_vless_inbound(1, [])])):
            assert await vpn.get_vpn_data(999) is None

    async def test_none_on_api_failure(self):
        async def fail(session, method, url, json_data=None):
            return (500, {"success": False}, "")

        with patch.object(vpn, "_request", new=fail):
            assert await vpn.get_vpn_data(100) is None

    async def test_none_on_network_exception(self):
        async def boom(session, method, url, json_data=None):
            raise ConnectionError("timeout")

        with patch.object(vpn, "_request", new=boom):
            assert await vpn.get_vpn_data(100) is None


# ===== create_user =====

class TestCreateUser:
    async def test_true_on_success_two_inbounds(self):
        cap: list = []
        with (
            patch.object(vpn, "_request", new=_fake_request(post_ok=True, capture=cap)),
            patch.object(vpn, "get_username", new=AsyncMock(return_value="tester")),
        ):
            assert await vpn.create_user(200, 30) is True
        add = [c for c in cap if c["url"].endswith("/addClient")]
        assert len(add) == 2  # VLESS_INBOUND_IDS=[1,2]

    async def test_false_on_api_error(self):
        with (
            patch.object(vpn, "_request", new=_fake_request(post_ok=False)),
            patch.object(vpn, "get_username", new=AsyncMock(return_value="t")),
        ):
            assert await vpn.create_user(201, 30) is False

    async def test_false_on_network_error(self):
        async def boom(session, method, url, json_data=None):
            raise ConnectionError

        with (
            patch.object(vpn, "_request", new=boom),
            patch.object(vpn, "get_username", new=AsyncMock(return_value="t")),
        ):
            assert await vpn.create_user(202, 30) is False

    async def test_payload_email_contains_user_id(self):
        cap: list = []
        with (
            patch.object(vpn, "_request", new=_fake_request(post_ok=True, capture=cap)),
            patch.object(vpn, "get_username", new=AsyncMock(return_value="t")),
        ):
            await vpn.create_user(203, 30)
        for payload in cap:
            for client in _clients_from(payload):
                assert "203" in client["email"]


# ===== disable / enable =====

class TestDisableEnable:
    async def test_disable_calls_update(self):
        inbounds = [_vless_inbound(1, [_vless_client(300)])]
        cap: list = []
        with patch.object(vpn, "_request", new=_fake_request(inbounds, capture=cap)):
            assert await vpn.disable_user(300) is True
        assert any("updateClient" in c["url"] for c in cap)

    async def test_disable_sets_enable_false(self):
        inbounds = [_vless_inbound(1, [_vless_client(301, enabled=True)])]
        cap: list = []
        with patch.object(vpn, "_request", new=_fake_request(inbounds, capture=cap)):
            await vpn.disable_user(301)
        for payload in cap:
            for c in _clients_from(payload):
                if "301" in c.get("email", ""):
                    assert c["enable"] is False

    async def test_disable_no_matching_client(self):
        inbounds = [_vless_inbound(1, [_vless_client(999)])]
        cap: list = []
        with patch.object(vpn, "_request", new=_fake_request(inbounds, capture=cap)):
            assert await vpn.disable_user(302) is False
        assert cap == []

    async def test_enable_sets_enable_true(self):
        inbounds = [_vless_inbound(1, [_vless_client(303, enabled=False)])]
        cap: list = []
        with patch.object(vpn, "_request", new=_fake_request(inbounds, capture=cap)):
            await vpn.enable_user(303)
        for payload in cap:
            for c in _clients_from(payload):
                if "303" in c.get("email", ""):
                    assert c["enable"] is True


# ===== extend =====

class TestExtendUser:
    async def test_increases_expiry(self):
        base = int(time.time() * 1000) + 10 * DAY_MS
        inbounds = [_vless_inbound(1, [_vless_client(210, expiry=base)])]
        cap: list = []
        with patch.object(vpn, "_request", new=_fake_request(inbounds, capture=cap)):
            assert await vpn.extend_user(210, 30) is True
        for payload in cap:
            for c in _clients_from(payload):
                if "210" in c.get("email", ""):
                    assert abs(c["expiryTime"] - (base + 30 * DAY_MS)) < 5000

    async def test_sets_enable_true(self):
        inbounds = [_vless_inbound(1, [_vless_client(211, enabled=False)])]
        cap: list = []
        with patch.object(vpn, "_request", new=_fake_request(inbounds, capture=cap)):
            await vpn.extend_user(211, 30)
        for payload in cap:
            for c in _clients_from(payload):
                if "211" in c.get("email", ""):
                    assert c["enable"] is True


# ===== delete =====

class TestDeleteUser:
    async def test_calls_del_client(self):
        inbounds = [_vless_inbound(1, [_vless_client(400)])]
        cap: list = []
        with patch.object(vpn, "_request", new=_fake_request(inbounds, capture=cap)):
            assert await vpn.delete_user(400) is True
        assert any("delClient" in c["url"] for c in cap)

    async def test_false_if_api_fails(self):
        inbounds = [_vless_inbound(1, [_vless_client(401)])]
        with patch.object(vpn, "_request", new=_fake_request(inbounds, post_ok=False)):
            assert await vpn.delete_user(401) is False


# ===== online =====

class TestOnline:
    async def test_returns_emails(self):
        with patch.object(
            vpn, "_request",
            new=_fake_request(online=["100_vless_1", "200_vless_2"]),
        ):
            assert await vpn.get_online_users() == ["100_vless_1", "200_vless_2"]

    async def test_empty_when_none(self):
        with patch.object(vpn, "_request", new=_fake_request(online=None)):
            assert await vpn.get_online_users() == []

    async def test_none_on_error(self):
        async def fail(session, method, url, json_data=None):
            return (500, {"success": False}, "")

        with patch.object(vpn, "_request", new=fail):
            assert await vpn.get_online_users() is None
