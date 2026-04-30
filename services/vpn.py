import requests
import json
import time
from uuid import uuid4
from config import PANEL_URL, USERNAME, PASSWORD, INBOUND_ID

# ✅ ОДНА сессия на всё
session = requests.Session()


# ===== LOGIN =====
def login():
    r = session.post(
        f"{PANEL_URL}/login",
        data={
            "username": USERNAME,
            "password": PASSWORD
        },
        verify=False
    )
    print("LOGIN:", r.status_code)


# ===== CREATE USER =====
def create_user(user_id, days):
    login()

    client_id = str(uuid4())
    expire = int((time.time() + days * 86400) * 1000)

    payload = {
        "id": INBOUND_ID,
        "settings": json.dumps({
            "clients": [{
                "id": client_id,
                "email": str(user_id),
                "limitIp": 1,
                "totalGB": 0,
                "expiryTime": expire
            }]
        })
    }

    r = session.post(
        f"{PANEL_URL}/panel/api/inbounds/addClient",
        json=payload,
        verify=False
    )

    print("CREATE STATUS:", r.status_code)
    print("RESPONSE:", r.text)

    try:
        data = r.json()
        if data.get("success"):
            return client_id
    except:
        print("❌ CREATE НЕ JSON")

    return None


# ===== FIND USER =====
def find_client(user_id):
    login()

    r = session.get(
        f"{PANEL_URL}/panel/api/inbounds/list",
        verify=False
    )

    print("LIST STATUS:", r.status_code)

    try:
        data = r.json()
    except:
        print("❌ НЕ JSON:")
        print(r.text)
        return None, None

    for inbound in data.get("obj", []):
        for client in inbound.get("clientStats", []):
            if client.get("email") == str(user_id):
                print("✅ Найден пользователь")
                print("UUID:", client.get("uuid"))
                print("INBOUND:", inbound.get("id"))
                return inbound.get("id"), client.get("uuid")

    print("❌ Пользователь не найден")
    return None, None


# ===== DELETE USER =====
def delete_user(user_id):
    inbound_id, uuid = find_client(user_id)

    if not uuid:
        return False

    url = f"{PANEL_URL}/panel/api/inbounds/{inbound_id}/delClient/{uuid}"

    r = session.post(url, verify=False)

    print("DELETE STATUS:", r.status_code)
    print("RESPONSE:", r.text)

    try:
        data = r.json()
        return data.get("success", False)
    except:
        return False