import requests
import json
import time
from uuid import uuid4
from config import PANEL_URL, PANEL_LOGIN, PANEL_PASSWORD, INBOUND_IDS, SUB_BASE_URL
from database.db import get_username


import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

session = requests.Session()


def login():
    session.cookies.clear()

    try:
        r = session.post(
            f"{PANEL_URL}/login",
            data={
                "username": PANEL_LOGIN,
                "password": PANEL_PASSWORD,
            },
            verify=False
        )

        print("LOGIN STATUS:", r.status_code)
        print("LOGIN RAW:", r.text[:200])

        return r.status_code == 200

    except Exception as e:
        print("LOGIN ERROR:", e)
        return False


def create_user(user_id, days):
    print("🔥 CREATE USER:", user_id)

    if not login():
        print("❌ LOGIN FAILED")
        return False

    expire = int((time.time() + days * 86400) * 1000)

    sub_id = str(uuid4()).replace("-", "")[:16]
    username = get_username(user_id) or f"user_{user_id}"

    success = False

    for inbound_id in INBOUND_IDS:

        client_uuid = str(uuid4())

        client_data = {
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
            "settings": json.dumps({
                "clients": [client_data]
            })
        }

        try:
            r = session.post(
                f"{PANEL_URL}/panel/api/inbounds/addClient",
                json=payload,
                verify=False
            )

            print("ADD STATUS:", r.status_code)
            print("ADD RAW:", r.text)

            if r.status_code == 200:
                success = True

        except Exception as e:
            print("ADD ERROR:", e)

    return success


def get_vpn_data(user_id):
    if not login():
        return None

    r = session.get(f"{PANEL_URL}/panel/api/inbounds/list", verify=False)

    try:
        data = r.json()
    except:
        return None

    for inbound in data.get("obj", []):
        for client in inbound.get("clientStats", []):
            if client.get("email", "").startswith(str(user_id)):
                sub_id = client.get("subId")
                if sub_id:
                    return f"{SUB_BASE_URL}/{sub_id}"

    return None


def get_inbounds():
    try:
        r = session.get(
            f"{PANEL_URL}/panel/api/inbounds/list",
            verify=False
        )

        print("LIST STATUS:", r.status_code)
        print("LIST RAW:", r.text[:300])

        return r.json()

    except Exception as e:
        print("LIST ERROR:", e)
        return None


#удаление пользователя
def delete_user(user_id):
    print("🔥 DELETE START:", user_id)

    if not login():
        print("❌ LOGIN FAILED")
        return False

    data = get_inbounds()
    if not data:
        return False

    success = False

    for inbound in (data or {}).get("obj", []):
        inbound_id = inbound["id"]

        for client in inbound.get("clientStats", []):
            email = client.get("email")
            uuid = client.get("uuid")

            # 🔥 ищем ТВОЕГО пользователя
            if str(user_id) in email:
                print("FOUND:", email, uuid)

                try:
                    url = f"{PANEL_URL}/panel/api/inbounds/{inbound_id}/delClient/{uuid}"

                    r = session.post(url, verify=False)

                    print("DELETE URL:", url)
                    print("STATUS:", r.status_code)
                    print("RAW:", r.text)

                    if r.status_code == 200:
                        success = True

                except Exception as e:
                    print("DELETE ERROR:", e)

    return success