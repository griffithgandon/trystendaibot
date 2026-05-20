import requests
import json
import time
from uuid import uuid4

from config import (
    PANEL_URL,
    API_TOKEN,
    VLESS_INBOUND_IDS,
    HYSTERIA_INBOUND_ID,
    HYSTERIA_ENABLED,
    SUB_BASE_URL,
    SSL_VERIFY,
)

from database.db import get_username

import urllib3
if SSL_VERIFY is False:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

session = requests.Session()

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json"
}

REQUEST_TIMEOUT = 10


# ===== GET INBOUNDS =====
def get_inbounds() -> dict | None:
    try:
        r = session.get(
            f"{PANEL_URL}/panel/api/inbounds/list",
            headers=HEADERS,
            verify=SSL_VERIFY,
            timeout=REQUEST_TIMEOUT
        )

        if r.status_code != 200:
            print("LIST ERROR STATUS:", r.status_code)
            return None

        return r.json()

    except Exception as e:
        print("LIST ERROR:", e)
        return None


# ===== CREATE USER =====
def create_user(user_id: int, days: int) -> bool:
    print("CREATE USER:", user_id)

    expire = int((time.time() + days * 86400) * 1000)
    username = get_username(user_id) or f"user_{user_id}"

    sub_id = str(uuid4()).replace("-", "")[:16]

    success = False

    # ===== VLESS =====
    vless_uuid = str(uuid4())

    for inbound_id in VLESS_INBOUND_IDS:
        vless_client = {
            "id": vless_uuid,
            "flow": "xtls-rprx-vision",
            "email": f"{user_id}_vless_{inbound_id}",
            "enable": True,
            "expiryTime": expire,
            "limitIp": 1,
            "totalGB": 0,
            "subId": sub_id,
            "comment": username
        }

        vless_payload = {
            "id": inbound_id,
            "settings": json.dumps({"clients": [vless_client]})
        }

        try:
            r = session.post(
                f"{PANEL_URL}/panel/api/inbounds/addClient",
                headers=HEADERS,
                json=vless_payload,
                verify=SSL_VERIFY,
                timeout=REQUEST_TIMEOUT
            )
            print(f"VLESS [{inbound_id}] STATUS:", r.status_code, r.text)

            if r.status_code == 200 and r.json().get("success"):
                success = True

        except Exception as e:
            print(f"VLESS [{inbound_id}] ERROR:", e)

    # ===== HYSTERIA2 =====
    if HYSTERIA_ENABLED:
        try:
            r = session.get(
                f"{PANEL_URL}/panel/api/inbounds/get/{HYSTERIA_INBOUND_ID}",
                headers=HEADERS,
                verify=SSL_VERIFY,
                timeout=REQUEST_TIMEOUT
            )
            print("HYSTERIA GET STATUS:", r.status_code)

            if r.status_code != 200 or not r.json().get("success"):
                print("HYSTERIA GET ERROR:", r.text)
            else:
                inbound_data = r.json()["obj"]
                settings = json.loads(inbound_data.get("settings", "{}"))
                clients = settings.get("clients", [])

                new_client = {
                    "password": str(uuid4()),
                    "email": f"{user_id}_hy2",
                    "enable": True,
                    "expiryTime": expire,
                    "limitIp": 1,
                    "totalGB": 0,
                    "subId": sub_id,
                    "comment": username
                }
                clients.append(new_client)
                settings["clients"] = clients
                inbound_data["settings"] = json.dumps(settings)

                r2 = session.post(
                    f"{PANEL_URL}/panel/api/inbounds/update/{HYSTERIA_INBOUND_ID}",
                    headers=HEADERS,
                    json=inbound_data,
                    verify=SSL_VERIFY,
                    timeout=REQUEST_TIMEOUT
                )
                print("HYSTERIA UPDATE STATUS:", r2.status_code, r2.text)

                if r2.status_code == 200 and r2.json().get("success"):
                    success = True

        except Exception as e:
            print("HYSTERIA ERROR:", e)
    else:
        print("HYSTERIA SKIP: HYSTERIA_ENABLED=False")

    return success


# ===== DISABLE USER =====
# Отключает клиента на панели (enable=false) без удаления.
# Используется при истечении подписки.
def disable_user(user_id: int) -> bool:
    print("DISABLE USER:", user_id)

    data = get_inbounds()
    if not data:
        return False

    success = False

    for inbound in data.get("obj", []):
        inbound_id = inbound.get("id")
        protocol = inbound.get("protocol", "").lower()

        # ── Hysteria2 ──────────────────────────────────────────────────────────
        if protocol in ("hysteria2", "hysteria"):
            try:
                r_get = session.get(
                    f"{PANEL_URL}/panel/api/inbounds/get/{inbound_id}",
                    headers=HEADERS,
                    verify=SSL_VERIFY,
                    timeout=REQUEST_TIMEOUT
                )

                if r_get.status_code != 200 or not r_get.json().get("success"):
                    print(f"DISABLE HY2 GET [{inbound_id}] ERROR:", r_get.text)
                    continue

                full_inbound = r_get.json()["obj"]
                full_settings = json.loads(full_inbound.get("settings", "{}"))

                updated = False
                for c in full_settings.get("clients", []):
                    if c.get("email", "").startswith(str(user_id)):
                        c["enable"] = False
                        updated = True

                if not updated:
                    continue

                full_inbound["settings"] = json.dumps(full_settings)

                r_upd = session.post(
                    f"{PANEL_URL}/panel/api/inbounds/update/{inbound_id}",
                    headers=HEADERS,
                    json=full_inbound,
                    verify=SSL_VERIFY,
                    timeout=REQUEST_TIMEOUT
                )
                print(f"DISABLE HY2 [{inbound_id}] STATUS:", r_upd.status_code, r_upd.text)

                if r_upd.status_code == 200 and r_upd.json().get("success"):
                    success = True

            except Exception as e:
                print(f"DISABLE HY2 [{inbound_id}] ERROR:", e)

        # ── VLESS / VMess ──────────────────────────────────────────────────────
        else:
            try:
                settings = json.loads(inbound.get("settings", "{}"))
            except Exception as e:
                print("SETTINGS JSON ERROR:", e)
                continue

            clients = settings.get("clients", [])
            target = [c for c in clients if c.get("email", "").startswith(str(user_id))]

            if not target:
                continue

            for client in target:
                client_id = client.get("id")
                if not client_id:
                    continue

                client["enable"] = False

                payload = {
                    "id": inbound_id,
                    "settings": json.dumps({"clients": [client]})
                }

                try:
                    r = session.post(
                        f"{PANEL_URL}/panel/api/inbounds/updateClient/{client_id}",
                        headers=HEADERS,
                        json=payload,
                        verify=SSL_VERIFY,
                        timeout=REQUEST_TIMEOUT
                    )
                    print(f"DISABLE VLESS [{inbound_id}] STATUS:", r.status_code, r.text)

                    if r.status_code == 200 and r.json().get("success"):
                        success = True

                except Exception as e:
                    print(f"DISABLE VLESS [{inbound_id}] ERROR:", e)

    return success


# ===== ENABLE USER =====
# Включает клиента обратно (enable=true).
# Используется при продлении подписки если юзер был отключён.
def enable_user(user_id: int) -> bool:
    print("ENABLE USER:", user_id)

    data = get_inbounds()
    if not data:
        return False

    success = False

    for inbound in data.get("obj", []):
        inbound_id = inbound.get("id")
        protocol = inbound.get("protocol", "").lower()

        # ── Hysteria2 ──────────────────────────────────────────────────────────
        if protocol in ("hysteria2", "hysteria"):
            try:
                r_get = session.get(
                    f"{PANEL_URL}/panel/api/inbounds/get/{inbound_id}",
                    headers=HEADERS,
                    verify=SSL_VERIFY,
                    timeout=REQUEST_TIMEOUT
                )

                if r_get.status_code != 200 or not r_get.json().get("success"):
                    continue

                full_inbound = r_get.json()["obj"]
                full_settings = json.loads(full_inbound.get("settings", "{}"))

                updated = False
                for c in full_settings.get("clients", []):
                    if c.get("email", "").startswith(str(user_id)):
                        c["enable"] = True
                        updated = True

                if not updated:
                    continue

                full_inbound["settings"] = json.dumps(full_settings)

                r_upd = session.post(
                    f"{PANEL_URL}/panel/api/inbounds/update/{inbound_id}",
                    headers=HEADERS,
                    json=full_inbound,
                    verify=SSL_VERIFY,
                    timeout=REQUEST_TIMEOUT
                )
                print(f"ENABLE HY2 [{inbound_id}] STATUS:", r_upd.status_code, r_upd.text)

                if r_upd.status_code == 200 and r_upd.json().get("success"):
                    success = True

            except Exception as e:
                print(f"ENABLE HY2 [{inbound_id}] ERROR:", e)

        # ── VLESS / VMess ──────────────────────────────────────────────────────
        else:
            try:
                settings = json.loads(inbound.get("settings", "{}"))
            except Exception:
                continue

            clients = settings.get("clients", [])
            target = [c for c in clients if c.get("email", "").startswith(str(user_id))]

            if not target:
                continue

            for client in target:
                client_id = client.get("id")
                if not client_id:
                    continue

                client["enable"] = True

                payload = {
                    "id": inbound_id,
                    "settings": json.dumps({"clients": [client]})
                }

                try:
                    r = session.post(
                        f"{PANEL_URL}/panel/api/inbounds/updateClient/{client_id}",
                        headers=HEADERS,
                        json=payload,
                        verify=SSL_VERIFY,
                        timeout=REQUEST_TIMEOUT
                    )
                    print(f"ENABLE VLESS [{inbound_id}] STATUS:", r.status_code, r.text)

                    if r.status_code == 200 and r.json().get("success"):
                        success = True

                except Exception as e:
                    print(f"ENABLE VLESS [{inbound_id}] ERROR:", e)

    return success


# ===== DELETE USER =====
# Полное удаление клиента с панели.
# Используется только при явном удалении через админку или пересоздании.
def delete_user(user_id: int) -> bool:
    print("DELETE USER:", user_id)

    data = get_inbounds()
    if not data:
        return False

    success = False

    for inbound in data.get("obj", []):
        inbound_id = inbound.get("id")
        protocol = inbound.get("protocol", "").lower()

        if protocol in ("hysteria2", "hysteria"):
            try:
                r_get = session.get(
                    f"{PANEL_URL}/panel/api/inbounds/get/{inbound_id}",
                    headers=HEADERS,
                    verify=SSL_VERIFY,
                    timeout=REQUEST_TIMEOUT
                )

                if r_get.status_code != 200 or not r_get.json().get("success"):
                    print(f"DELETE HY2 GET [{inbound_id}] ERROR:", r_get.text)
                    continue

                full_inbound = r_get.json()["obj"]
                full_settings = json.loads(full_inbound.get("settings", "{}"))

                clients_before = full_settings.get("clients", [])
                clients_after = [
                    c for c in clients_before
                    if not c.get("email", "").startswith(str(user_id))
                ]

                removed = len(clients_before) - len(clients_after)
                if removed == 0:
                    continue

                full_settings["clients"] = clients_after
                full_inbound["settings"] = json.dumps(full_settings)

                r_upd = session.post(
                    f"{PANEL_URL}/panel/api/inbounds/update/{inbound_id}",
                    headers=HEADERS,
                    json=full_inbound,
                    verify=SSL_VERIFY,
                    timeout=REQUEST_TIMEOUT
                )
                print(f"DELETE HY2 UPDATE [{inbound_id}] STATUS:", r_upd.status_code, r_upd.text)

                if r_upd.status_code == 200 and r_upd.json().get("success"):
                    success = True

            except Exception as e:
                print(f"DELETE HY2 [{inbound_id}] ERROR:", e)

        else:
            try:
                settings = json.loads(inbound.get("settings", "{}"))
            except Exception as e:
                print("SETTINGS JSON ERROR:", e)
                continue

            clients = settings.get("clients", [])
            target = [c for c in clients if c.get("email", "").startswith(str(user_id))]

            if not target:
                continue

            for client in target:
                client_id = client.get("id")
                if not client_id:
                    continue

                try:
                    r = session.post(
                        f"{PANEL_URL}/panel/api/inbounds/{inbound_id}/delClient/{client_id}",
                        headers=HEADERS,
                        verify=SSL_VERIFY,
                        timeout=REQUEST_TIMEOUT
                    )
                    print(f"DELETE VLESS [{inbound_id}] STATUS:", r.status_code, r.text)

                    if r.status_code == 200 and r.json().get("success"):
                        success = True

                except Exception as e:
                    print(f"DELETE VLESS [{inbound_id}] ERROR:", e)

    return success


# ===== GET VPN DATA (subscription URL) =====
def get_vpn_data(user_id: int) -> str | None:
    data = get_inbounds()
    if not data:
        return None

    for inbound in data.get("obj", []):
        try:
            settings = json.loads(inbound.get("settings", "{}"))
        except Exception:
            continue

        for client in settings.get("clients", []):
            email = client.get("email", "")

            if email.startswith(str(user_id)):
                sub_id = client.get("subId")

                if sub_id:
                    return f"{SUB_BASE_URL}/{sub_id}"

    return None


# ===== ONLINE USERS =====
def get_online_users() -> list[str] | None:
    try:
        r = session.post(
            f"{PANEL_URL}/panel/api/inbounds/onlines",
            headers=HEADERS,
            verify=SSL_VERIFY,
            timeout=REQUEST_TIMEOUT
        )

        if r.status_code != 200:
            print("ONLINE ERROR STATUS:", r.status_code)
            return None

        data = r.json()
        return data.get("obj") or []

    except Exception as e:
        print("ONLINE ERROR:", e)
        return None


# ===== EXTEND USER =====
def extend_user(user_id: int, days: int) -> bool:
    print("EXTEND USER:", user_id)

    data = get_inbounds()
    if not data:
        return False

    success = False
    now_ms = int(time.time() * 1000)

    for inbound in data.get("obj", []):
        inbound_id = inbound.get("id")
        protocol = inbound.get("protocol", "").lower()

        try:
            settings = json.loads(inbound.get("settings", "{}"))
        except Exception:
            continue

        for client in settings.get("clients", []):
            email = client.get("email", "")

            if not email.startswith(str(user_id)):
                continue

            current_expiry = client.get("expiryTime", 0)
            new_expiry = (
                current_expiry + days * 86400 * 1000
                if current_expiry > now_ms
                else now_ms + days * 86400 * 1000
            )
            client["expiryTime"] = new_expiry
            # При продлении всегда включаем клиента обратно
            client["enable"] = True

            if protocol in ("hysteria2", "hysteria"):
                try:
                    r_get = session.get(
                        f"{PANEL_URL}/panel/api/inbounds/get/{inbound_id}",
                        headers=HEADERS,
                        verify=SSL_VERIFY,
                        timeout=REQUEST_TIMEOUT
                    )
                    if r_get.status_code != 200 or not r_get.json().get("success"):
                        print(f"EXTEND HY2 GET [{inbound_id}] ERROR:", r_get.text)
                        continue

                    full_inbound = r_get.json()["obj"]
                    full_settings = json.loads(full_inbound.get("settings", "{}"))

                    updated = False
                    for c in full_settings.get("clients", []):
                        if c.get("email", "").startswith(str(user_id)):
                            cur = c.get("expiryTime", 0)
                            c["expiryTime"] = (
                                cur + days * 86400 * 1000
                                if cur > now_ms
                                else now_ms + days * 86400 * 1000
                            )
                            c["enable"] = True
                            updated = True

                    if not updated:
                        continue

                    full_inbound["settings"] = json.dumps(full_settings)

                    r_upd = session.post(
                        f"{PANEL_URL}/panel/api/inbounds/update/{inbound_id}",
                        headers=HEADERS,
                        json=full_inbound,
                        verify=SSL_VERIFY,
                        timeout=REQUEST_TIMEOUT
                    )
                    print(f"EXTEND HY2 [{inbound_id}] STATUS:", r_upd.status_code, r_upd.text)

                    if r_upd.status_code == 200 and r_upd.json().get("success"):
                        success = True

                except Exception as e:
                    print("EXTEND HY2 ERROR:", e)

            else:
                client_uuid = client.get("id")
                if not client_uuid:
                    continue

                payload = {
                    "id": inbound_id,
                    "settings": json.dumps({"clients": [client]})
                }

                try:
                    r = session.post(
                        f"{PANEL_URL}/panel/api/inbounds/updateClient/{client_uuid}",
                        headers=HEADERS,
                        json=payload,
                        verify=SSL_VERIFY,
                        timeout=REQUEST_TIMEOUT
                    )
                    print(f"EXTEND VLESS [{inbound_id}] STATUS:", r.status_code, r.text)

                    if r.status_code == 200 and r.json().get("success"):
                        success = True

                except Exception as e:
                    print("EXTEND VLESS ERROR:", e)

    return success