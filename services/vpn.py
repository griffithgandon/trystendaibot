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

    # Один subId на оба протокола — подписка работает через VLESS-inbound
    sub_id = str(uuid4()).replace("-", "")[:16]

    success = False

    # ===== VLESS (все inbound'ы из списка) =====
    # Один UUID и email на все inbound'ы — subId общий
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
    # addClient не работает с hysteria2 в 3x-ui ("empty client ID").
    # Решение: получаем inbound, дописываем клиента в settings, обновляем весь inbound.
    if HYSTERIA_ENABLED:
        try:
            # 1. Получаем текущий inbound
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

                # 2. Парсим settings и добавляем нового клиента
                settings = json.loads(inbound_data.get("settings", "{}"))
                clients  = settings.get("clients", [])

                new_client = {
                    "password": str(uuid4()),
                    "email":    f"{user_id}_hy2",
                    "enable":   True,
                    "expiryTime": expire,
                    "limitIp":  1,
                    "totalGB":  0,
                    "comment":  username
                }
                clients.append(new_client)
                settings["clients"] = clients
                inbound_data["settings"] = json.dumps(settings)

                # 3. Обновляем inbound целиком
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


# ===== DELETE USER =====
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
            # delClient не работает для hysteria2.
            # Всегда делаем отдельный GET — list может не содержать клиентов в settings.
            try:
                r_get = session.get(
                    f"{PANEL_URL}/panel/api/inbounds/get/{inbound_id}",
                    headers=HEADERS,
                    verify=SSL_VERIFY,
                    timeout=REQUEST_TIMEOUT
                )
                print(f"DELETE HY2 GET [{inbound_id}] STATUS:", r_get.status_code)

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
                print(f"DELETE HY2 [{inbound_id}]: найдено клиентов={len(clients_before)}, убрано={removed}")

                if removed == 0:
                    continue  # этого пользователя нет в inbound — пропускаем

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
            # VLESS/VMess: стандартный delClient
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
                print("FOUND:", client.get("email"), "client_id:", client_id)

                if not client_id:
                    print("SKIP: no client_id for", client.get("email"))
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
# subId хранится в settings.clients, не в clientStats
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
    """
    Возвращает список email'ов клиентов онлайн.
    3x-ui: POST /panel/api/inbounds/onlines
    """
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

            if protocol in ("hysteria2", "hysteria"):
                # Hysteria2: updateClient не работает — обновляем весь inbound
                settings["clients"] = [
                    c if c.get("email") != email else client
                    for c in settings.get("clients", [])
                ]
                inbound["settings"] = json.dumps(settings)

                try:
                    r = session.post(
                        f"{PANEL_URL}/panel/api/inbounds/update/{inbound_id}",
                        headers=HEADERS,
                        json=inbound,
                        verify=SSL_VERIFY,
                        timeout=REQUEST_TIMEOUT
                    )
                    print(f"EXTEND HY2 [{inbound_id}] STATUS:", r.status_code, r.text)

                    if r.status_code == 200 and r.json().get("success"):
                        success = True

                except Exception as e:
                    print("EXTEND HY2 ERROR:", e)

            else:
                # VLESS/VMess: стандартный updateClient
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