import requests
import json
import time
from uuid import uuid4

from config import (
    PANEL_URL,
    API_TOKEN,
    INBOUND_IDS,
    SUB_BASE_URL,
)

from database.db import get_username

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

session = requests.Session()

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json"
}

# Таймаут для всех запросов к панели (сек)
REQUEST_TIMEOUT = 10


# ===== GET INBOUNDS =====
def get_inbounds() -> dict | None:
    try:
        r = session.get(
            f"{PANEL_URL}/panel/api/inbounds/list",
            headers=HEADERS,
            verify=False,
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

    for inbound_id in INBOUND_IDS:
        client_uuid = str(uuid4())

        client = {
            "id": client_uuid,
            "email": f"{user_id}_{inbound_id}",
            "enable": True,
            "expiryTime": expire,
            "limitIp": 1,
            "totalGB": 0,
            "subId": sub_id,
            "comment": username
        }

        payload = {
            "id": inbound_id,
            "settings": json.dumps({"clients": [client]})
        }

        try:
            r = session.post(
                f"{PANEL_URL}/panel/api/inbounds/addClient",
                headers=HEADERS,
                json=payload,
                verify=False,
                timeout=REQUEST_TIMEOUT
            )

            print("ADD STATUS:", r.status_code)

            if r.status_code == 200:
                success = True

        except Exception as e:
            print("ADD ERROR:", e)

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

        try:
            settings = json.loads(inbound.get("settings", "{}"))
        except Exception as e:
            print("SETTINGS JSON ERROR:", e)
            continue

        for client in settings.get("clients", []):
            email = client.get("email", "")
            client_id = client.get("id")

            if not email.startswith(str(user_id)):
                continue

            print("FOUND:", email, client_id)

            try:
                r = session.post(
                    f"{PANEL_URL}/panel/api/inbounds/{inbound_id}/delClient/{client_id}",
                    headers=HEADERS,
                    verify=False,
                    timeout=REQUEST_TIMEOUT
                )

                if r.status_code == 200:
                    success = True

            except Exception as e:
                print("DELETE ERROR:", e)

    return success


# ===== GET SUB =====
# БАГ в оригинале: subId искался в clientStats, где его нет.
# subId хранится в settings.clients — ищем там.
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
    Возвращает список email'ов клиентов, активных прямо сейчас.
    3x-ui: POST /panel/api/inbounds/onlines
    """
    try:
        r = session.post(
            f"{PANEL_URL}/panel/api/inbounds/onlines",
            headers=HEADERS,
            verify=False,
            timeout=REQUEST_TIMEOUT
        )

        if r.status_code != 200:
            print("ONLINE ERROR STATUS:", r.status_code)
            return None

        data = r.json()
        # API возвращает {"success": true, "obj": ["email1", "email2", ...]}
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

        try:
            settings = json.loads(inbound.get("settings", "{}"))
        except Exception:
            continue

        for client in settings.get("clients", []):
            email = client.get("email", "")

            if not email.startswith(str(user_id)):
                continue

            client_uuid = client.get("id")
            current_expiry = client.get("expiryTime", 0)

            # Прибавляем дни к текущей дате истечения, а не к now
            new_expiry = (
                current_expiry + days * 86400 * 1000
                if current_expiry > now_ms
                else now_ms + days * 86400 * 1000
            )

            client["expiryTime"] = new_expiry

            payload = {
                "id": inbound_id,
                "settings": json.dumps({"clients": [client]})
            }

            try:
                r = session.post(
                    f"{PANEL_URL}/panel/api/inbounds/updateClient/{client_uuid}",
                    headers=HEADERS,
                    json=payload,
                    verify=False,
                    timeout=REQUEST_TIMEOUT
                )

                print("EXTEND STATUS:", r.status_code)

                if r.status_code == 200:
                    success = True

            except Exception as e:
                print("EXTEND ERROR:", e)

    return success