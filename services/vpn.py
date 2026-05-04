import requests
import json
import time
from uuid import uuid4
from config import PANEL_URL, USERNAME, PASSWORD, INBOUND_IDS, SUB_BASE_URL
from database.database import get_username

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

session = requests.Session()


# ===== LOGIN =====
def login():
    session.cookies.clear()

    r = session.post(
        f"{PANEL_URL}/login",
        data={
            "username": USERNAME,
            "password": PASSWORD
        },
        verify=False,
        timeout=10
    )

    try:
        data = r.json()
        if not data.get("success"):
            print("❌ LOGIN FAILED:", data)
            return False
    except:
        print("❌ LOGIN ERROR:", r.text)
        return False

    print("✅ LOGIN OK")
    return True


# ===== CREATE USER =====
def create_user(user_id, days):
    if not login():
        return False

    expire = int((time.time() + days * 86400) * 1000)

    # 🔥 один subId на все inbound
    sub_id = str(uuid4()).replace("-", "")[:16]

    # 🔥 берём ник из БД
    username = get_username(user_id) or "no_name"

    for inbound_id in INBOUND_IDS:

        client_uuid = str(uuid4())

        payload = {
            "id": inbound_id,
            "settings": json.dumps({
                "clients": [{
                    "id": client_uuid,
                    "email": f"{user_id}_{inbound_id}",
                    "limitIp": 1,
                    "totalGB": 0,
                    "expiryTime": expire,
                    "enable": True,
                    "subId": sub_id,
                    "comment": username  # 🔥 НИК В ПАНЕЛЬ
                }]
            })
        }

        try:
            r = session.post(
                f"{PANEL_URL}/panel/api/inbounds/addClient",
                json=payload,
                verify=False,
                timeout=10
            )

            print(f"ADD → {inbound_id}:", r.status_code, r.text)

        except Exception as e:
            print(f"❌ ERROR ADD {inbound_id}:", e)

    return True


# ===== DELETE USER =====
def delete_user(user_id):
    if not login():
        return False

    try:
        r = session.get(
            f"{PANEL_URL}/panel/api/inbounds/list",
            verify=False,
            timeout=10
        )
        data = r.json()
    except:
        return False

    success = False

    for inbound in data.get("obj", []):
        inbound_id = inbound.get("id")

        for client in inbound.get("clientStats", []):
            if client.get("email", "").startswith(str(user_id)):

                uuid = client.get("uuid")

                try:
                    r = session.post(
                        f"{PANEL_URL}/panel/api/inbounds/{inbound_id}/delClient/{uuid}",
                        verify=False,
                        timeout=10
                    )

                    print(f"DELETE → {inbound_id}:", r.status_code)

                    if r.json().get("success"):
                        success = True

                except:
                    pass

    return success


# ===== GET SUB LINK =====
def get_vpn_data(user_id):
    if not login():
        return None

    try:
        r = session.get(
            f"{PANEL_URL}/panel/api/inbounds/list",
            verify=False,
            timeout=10
        )
        data = r.json()
    except:
        return None

    sub_id = None

    for inbound in data.get("obj", []):
        for client in inbound.get("clientStats", []):
            if client.get("email", "").startswith(str(user_id)):
                if not sub_id:
                    sub_id = client.get("subId")

    if not sub_id:
        return None

    return f"{SUB_BASE_URL}/{sub_id}"