import requests
import json
import time
from uuid import uuid4
from config import PANEL_URL, USERNAME, PASSWORD, INBOUND_IDS, SUB_BASE_URL
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
                "username": USERNAME,
                "password": PASSWORD
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
    if not login():
        return False

    expire = int((time.time() + days * 86400) * 1000)
    sub_id = str(uuid4()).replace("-", "")[:16]

    success = False

    for inbound_id in INBOUND_IDS:

        client = {
            "id": str(uuid4()),
            "email": f"{user_id}_{inbound_id}",
            "limitIp": 1,
            "totalGB": 0,
            "expiryTime": expire,
            "enable": True,
            "subId": sub_id
        }

        payload = {
            "id": inbound_id,
            "settings": json.dumps({
                "clients": [client]
            })
        }

        try:
            r = session.post(
                f"{PANEL_URL}/xui/inbound/addClient",
                json=payload,
                verify=False
            )

            print("CREATE:", r.status_code, r.text)

            if r.status_code == 200:
                success = True

        except Exception as e:
            print("CREATE ERROR:", e)

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

    for inbound in data.get("obj", []):
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