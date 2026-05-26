"""
Тесты для services/vpn.py

Все HTTP-запросы к 3X-UI панели мокируются.
"""

import importlib.util
import json
import sys
import os
import time
import types as builtin_types
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_VPN_SOURCE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "services", "vpn.py"
)


def _load_vpn_module():
    fake_config = builtin_types.ModuleType("config")
    fake_config.PANEL_URL = "https://panel.example.com"
    fake_config.API_TOKEN = "test_token"
    fake_config.VLESS_INBOUND_IDS = [1, 2]
    fake_config.HYSTERIA_INBOUND_ID = 3
    fake_config.HYSTERIA_ENABLED = False
    fake_config.SUB_BASE_URL = "https://sub.example.com/sub"
    fake_config.SSL_VERIFY = False
    sys.modules["config"] = fake_config

    fake_db = builtin_types.ModuleType("database.db")
    fake_db.get_username = lambda uid: f"user_{uid}"
    if "database" not in sys.modules or not hasattr(sys.modules["database"], "__path__"):
        import database
        sys.modules["database"] = database
    sys.modules["database.db"] = fake_db

    spec = importlib.util.spec_from_file_location("_test_vpn", _VPN_SOURCE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def vpn():
    return _load_vpn_module()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(obj=None):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"success": True, "obj": obj or []}
    return r

def _fail(status=500):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = {"success": False}
    return r

def _inbounds(inbounds: list):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"success": True, "obj": inbounds}
    return r

def _vless_inbound(inbound_id: int, clients: list):
    return {"id": inbound_id, "protocol": "vless", "settings": json.dumps({"clients": clients})}

def _vless_client(user_id: int, enabled: bool = True, sub_id: str = "abc123"):
    return {
        "id": f"uuid-{user_id}",
        "email": f"{user_id}_vless_1",
        "enable": enabled,
        "expiryTime": int(time.time() * 1000) + 86400 * 1000 * 30,
        "subId": sub_id,
    }


# ---------------------------------------------------------------------------
# get_vpn_data
# ---------------------------------------------------------------------------

class TestGetVpnData:
    def test_returns_sub_url_when_client_found(self, vpn):
        client = _vless_client(100, sub_id="mysub")
        with patch.object(vpn.session, "get", return_value=_inbounds([_vless_inbound(1, [client])])):
            assert vpn.get_vpn_data(100) == "https://sub.example.com/sub/mysub"

    def test_returns_none_when_client_not_found(self, vpn):
        with patch.object(vpn.session, "get", return_value=_inbounds([_vless_inbound(1, [])])):
            assert vpn.get_vpn_data(999) is None

    def test_returns_none_on_api_failure(self, vpn):
        with patch.object(vpn.session, "get", return_value=_fail()):
            assert vpn.get_vpn_data(100) is None

    def test_returns_none_on_network_exception(self, vpn):
        with patch.object(vpn.session, "get", side_effect=ConnectionError("timeout")):
            assert vpn.get_vpn_data(100) is None


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------

class TestCreateUser:
    def test_returns_true_on_success(self, vpn):
        with patch.object(vpn.session, "post", return_value=_ok()) as mock_post:
            assert vpn.create_user(200, 30) is True
        # VLESS_INBOUND_IDS = [1, 2] → два POST
        assert mock_post.call_count == 2

    def test_returns_false_on_api_error(self, vpn):
        with patch.object(vpn.session, "post", return_value=_fail()):
            assert vpn.create_user(201, 30) is False

    def test_returns_false_on_network_error(self, vpn):
        with patch.object(vpn.session, "post", side_effect=ConnectionError):
            assert vpn.create_user(202, 30) is False

    def test_post_payload_contains_user_id_in_email(self, vpn):
        captured = []
        def fake_post(url, **kwargs):
            captured.append(kwargs.get("json", {}))
            return _ok()
        with patch.object(vpn.session, "post", side_effect=fake_post):
            vpn.create_user(203, 30)
        for payload in captured:
            clients = json.loads(payload.get("settings", "{}")).get("clients", [])
            if clients:
                assert str(203) in clients[0]["email"]


# ---------------------------------------------------------------------------
# disable_user / enable_user
# ---------------------------------------------------------------------------

class TestDisableEnableUser:
    def test_disable_user_calls_update_endpoint(self, vpn):
        inbounds = [_vless_inbound(1, [_vless_client(300)])]
        with patch.object(vpn.session, "get", return_value=_inbounds(inbounds)), \
             patch.object(vpn.session, "post", return_value=_ok()) as mock_post:
            assert vpn.disable_user(300) is True
        assert mock_post.called

    def test_disable_user_sets_enable_false(self, vpn):
        inbounds = [_vless_inbound(1, [_vless_client(301, enabled=True)])]
        sent = []
        def fake_post(url, **kwargs):
            sent.append(kwargs.get("json", {}))
            return _ok()
        with patch.object(vpn.session, "get", return_value=_inbounds(inbounds)), \
             patch.object(vpn.session, "post", side_effect=fake_post):
            vpn.disable_user(301)
        for payload in sent:
            for c in json.loads(payload.get("settings", "{}")).get("clients", []):
                if str(301) in c.get("email", ""):
                    assert c["enable"] is False

    def test_disable_user_no_matching_client(self, vpn):
        inbounds = [_vless_inbound(1, [_vless_client(999)])]
        with patch.object(vpn.session, "get", return_value=_inbounds(inbounds)), \
             patch.object(vpn.session, "post", return_value=_ok()) as mock_post:
            result = vpn.disable_user(302)
        assert mock_post.call_count == 0
        assert result is False

    def test_enable_user_sets_enable_true(self, vpn):
        inbounds = [_vless_inbound(1, [_vless_client(303, enabled=False)])]
        sent = []
        def fake_post(url, **kwargs):
            sent.append(kwargs.get("json", {}))
            return _ok()
        with patch.object(vpn.session, "get", return_value=_inbounds(inbounds)), \
             patch.object(vpn.session, "post", side_effect=fake_post):
            vpn.enable_user(303)
        for payload in sent:
            for c in json.loads(payload.get("settings", "{}")).get("clients", []):
                if str(303) in c.get("email", ""):
                    assert c["enable"] is True


# ---------------------------------------------------------------------------
# extend_user
# ---------------------------------------------------------------------------

class TestExtendUser:
    def test_extend_increases_expiry(self, vpn):
        now_ms = int(time.time() * 1000)
        client = _vless_client(200)
        client["expiryTime"] = now_ms + 86400 * 1000 * 10
        inbounds = [_vless_inbound(1, [client])]
        sent = []
        def fake_post(url, **kwargs):
            sent.append(kwargs.get("json", {}))
            return _ok()
        with patch.object(vpn.session, "get", return_value=_inbounds(inbounds)), \
             patch.object(vpn.session, "post", side_effect=fake_post):
            assert vpn.extend_user(200, 30) is True
        for payload in sent:
            for c in json.loads(payload.get("settings", "{}")).get("clients", []):
                if str(200) in c.get("email", ""):
                    expected = client["expiryTime"] + 30 * 86400 * 1000
                    assert abs(c["expiryTime"] - expected) < 5000

    def test_extend_sets_enable_true(self, vpn):
        inbounds = [_vless_inbound(1, [_vless_client(201, enabled=False)])]
        sent = []
        def fake_post(url, **kwargs):
            sent.append(kwargs.get("json", {}))
            return _ok()
        with patch.object(vpn.session, "get", return_value=_inbounds(inbounds)), \
             patch.object(vpn.session, "post", side_effect=fake_post):
            vpn.extend_user(201, 30)
        for payload in sent:
            for c in json.loads(payload.get("settings", "{}")).get("clients", []):
                if str(201) in c.get("email", ""):
                    assert c["enable"] is True


# ---------------------------------------------------------------------------
# delete_user
# ---------------------------------------------------------------------------

class TestDeleteUser:
    def test_delete_calls_del_client_endpoint(self, vpn):
        inbounds = [_vless_inbound(1, [_vless_client(400)])]
        with patch.object(vpn.session, "get", return_value=_inbounds(inbounds)), \
             patch.object(vpn.session, "post", return_value=_ok()) as mock_post:
            assert vpn.delete_user(400) is True
        assert "delClient" in mock_post.call_args[0][0]

    def test_delete_returns_false_if_api_fails(self, vpn):
        inbounds = [_vless_inbound(1, [_vless_client(401)])]
        with patch.object(vpn.session, "get", return_value=_inbounds(inbounds)), \
             patch.object(vpn.session, "post", return_value=_fail()):
            assert vpn.delete_user(401) is False


# ---------------------------------------------------------------------------
# get_online_users
# ---------------------------------------------------------------------------

class TestGetOnlineUsers:
    def test_returns_list_of_emails(self, vpn):
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = {"success": True, "obj": ["100_vless_1", "200_vless_2"]}
        with patch.object(vpn.session, "post", return_value=r):
            assert vpn.get_online_users() == ["100_vless_1", "200_vless_2"]

    def test_returns_empty_list_when_nobody_online(self, vpn):
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = {"success": True, "obj": None}
        with patch.object(vpn.session, "post", return_value=r):
            assert vpn.get_online_users() == []

    def test_returns_none_on_error(self, vpn):
        with patch.object(vpn.session, "post", return_value=_fail()):
            assert vpn.get_online_users() is None